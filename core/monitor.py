import time
import threading
from datetime import datetime, timezone

import db as _db
from core.beacon import callsign_to_name, gs_token_to_name, pt_slug_to_name
from core.bot import bot_thread
from core.config import OGN_PREFIXES
from core.emergency import get_config
from core.notify import notify
from core.ogn import ogn_thread
from core.puretrack import pt_poll_loop
from core.state_machine import DeviceState, EventKind, State, check_timeouts

_RELOAD_SEC     = 120   # hot-reload interval
_ogn_reconnect  = threading.Event()

# The live devices dict, shared with the ingest route (push sources arrive on
# the web worker, not on a poller thread of ours).
_devices: dict = {}


def get_devices() -> dict:
    return _devices


_refresh_lock = threading.Lock()
_last_refresh = 0.0
_REFRESH_MIN_SEC = 10   # floor between on-demand rebuilds


def refresh_devices() -> None:
    """
    Rebuild the index now instead of waiting for the next hot-reload tick. Used
    by the ingest route when it sees an unknown token: a pilot who has just
    created one should not wait two minutes (nor should an unknown token let a
    caller hammer the DB — hence the floor).
    """
    global _last_refresh
    with _refresh_lock:
        now = time.monotonic()
        if now - _last_refresh < _REFRESH_MIN_SEC:
            return
        _last_refresh = now
        _update_devices(_devices)


def _build_index(device_rows: list) -> dict:
    """
    Build devices dict from scratch at startup.
    Also populates callsign_to_name, pt_slug_to_name and gs_token_to_name in
    core.beacon.
    """
    callsign_to_name.clear()
    pt_slug_to_name.clear()
    gs_token_to_name.clear()

    devices: dict[str, DeviceState] = {}

    for row in device_rows:
        name    = row["display_name"]
        sources = row["sources"]
        state   = DeviceState(device_id=name, name=name)

        for src_key, pfx in OGN_PREFIXES.items():
            if src_key in sources:
                callsign               = f"{pfx}{sources[src_key].upper()}"
                callsign_to_name[callsign] = name
                devices[callsign]          = state

        if "puretrack" in sources:
            slug                  = sources["puretrack"]
            pt_slug_to_name[slug] = name
            devices[f"PT_{slug}"] = state

        if "grappasafe" in sources:
            token                    = sources["grappasafe"]
            gs_token_to_name[token]  = name
            devices[f"GS_{token}"]   = state

    return devices


def _update_devices(devices: dict) -> None:
    """
    Hot-reload from DB every _RELOAD_SEC seconds.
    - Rebuilds callsign_to_name / pt_slug_to_name / gs_token_to_name (so removed
      devices stop being parsed, and a revoked ingest token stops being accepted).
    - Adds new device keys to `devices` dict, reusing existing DeviceState when possible.
    - Does NOT remove old keys — stale entries just never receive new beacons.
    """
    try:
        device_rows = _db.get_all_watched_devices()
    except Exception as e:
        print(f"  [monitor] reload error: {e}")
        return

    # name → existing state (deduplicated)
    name_to_state: dict[str, DeviceState] = {}
    for state in devices.values():
        if state.name not in name_to_state:
            name_to_state[state.name] = state

    callsign_to_name.clear()
    pt_slug_to_name.clear()
    gs_token_to_name.clear()

    added_ogn = 0
    added_pt  = 0
    added_gs  = 0
    for row in device_rows:
        name    = row["display_name"]
        sources = row["sources"]
        state   = name_to_state.get(name) or DeviceState(device_id=name, name=name)

        for src_key, pfx in OGN_PREFIXES.items():
            if src_key in sources:
                callsign               = f"{pfx}{sources[src_key].upper()}"
                callsign_to_name[callsign] = name
                if callsign not in devices:
                    devices[callsign] = state
                    added_ogn += 1

        if "puretrack" in sources:
            slug                  = sources["puretrack"]
            pt_slug_to_name[slug] = name
            pt_key                = f"PT_{slug}"
            if pt_key not in devices:
                devices[pt_key] = state
                added_pt += 1

        if "grappasafe" in sources:
            token                   = sources["grappasafe"]
            gs_token_to_name[token] = name
            gs_key                  = f"GS_{token}"
            if gs_key not in devices:
                devices[gs_key] = state
                added_gs += 1

    added = added_ogn + added_pt + added_gs
    if added:
        print(f"  [monitor] reload: +{added} new device keys ({len(device_rows)} total)")
        if added_ogn > 0:
            _ogn_reconnect.set()
            print(f"  [monitor] OGN filter update triggered ({added_ogn} new callsigns)")
    else:
        print(f"  [monitor] reload: {len(device_rows)} devices, no changes")


def _warm_start(devices: dict) -> None:
    """
    Seed DeviceState from the last known DB beacons so the bot survives container restarts.
    - older than signal_lost_min: state = SIGNAL_LOST, last_beacon populated
    - within it: leave UNKNOWN; the next live beacon will settle the state
    """
    from core.beacon import Beacon

    signal_lost_min = get_config().signal_lost_min

    name_to_state: dict[str, DeviceState] = {}
    for dev in devices.values():
        if dev.name not in name_to_state:
            name_to_state[dev.name] = dev

    now    = datetime.now(timezone.utc)
    seeded = 0
    for name, dev in name_to_state.items():
        row = _db.get_last_beacon_for_name(name)
        if not row:
            continue
        try:
            ts = datetime.fromisoformat(row["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_s = (now - ts).total_seconds()
        except Exception:
            continue

        beacon = Beacon(
            device_id  = row.get("device_id") or name,
            name       = name,
            source     = row.get("source", "db"),
            ts         = ts,
            lat        = float(row.get("lat") or 0),
            lon        = float(row.get("lon") or 0),
            alt_m      = float(row.get("alt_m") or 0),
            agl_m      = float(row.get("agl_m") or 0),
            speed_kmh  = float(row.get("speed_kmh") or 0),
            vspeed_ms  = float(row.get("vspeed_ms") or 0),
            course_deg = float(row.get("course_deg") or 0),
        )
        dev.last_beacon = beacon
        dev.last_seen   = ts

        if age_s > signal_lost_min * 60:
            dev.state = State.SIGNAL_LOST
            # Nothing was announced before the restart, so the recovery must
            # stay quiet too, and the device must not come back as GROUNDED.
            dev.state_before_lost = None
            dev.lost_announced    = False
        seeded += 1

    if seeded:
        print(f"  [monitor] warm-start: {seeded} devices seeded from DB")


def _timeout_loop(devices: dict, stop_flag) -> None:
    last_reload = time.monotonic() - _RELOAD_SEC   # trigger reload on first tick
    while not stop_flag.is_set():
        now    = datetime.now(timezone.utc)
        events = check_timeouts(devices, now, get_config())
        for ev in events:
            if ev.kind == EventKind.SIGNAL_LOST:
                _db.set_device_state(ev.beacon.name, "SIGNAL_LOST")
        if events:
            notify(events)
        if time.monotonic() - last_reload >= _RELOAD_SEC:
            _update_devices(devices)
            last_reload = time.monotonic()
        # 30s, not 60: this sweep also runs Path 2 of the reserve watch (a
        # descent that ended in silence), which must not wait a whole minute
        # past its own timeout.
        stop_flag.wait(30)


def start_monitor(stop_flag) -> list:
    """
    Load watched devices from webapp.db, start OGN / PT / bot / timeout threads.
    Returns the list of started Thread objects.
    """
    global _devices
    device_rows = _db.get_all_watched_devices()
    devices     = _build_index(device_rows)
    _devices    = devices
    _warm_start(devices)

    if not devices:
        print("  [monitor] no watched devices in DB — threads not started")
        print("  [monitor] hint: add users to a watchlist and assign devices to them")
        return []

    ogn_keys = [k for k in devices if not k.startswith(("PT_", "GS_"))]
    pt_keys  = [k for k in devices if k.startswith("PT_")]

    threads = []

    if ogn_keys:
        t = threading.Thread(
            target=ogn_thread,
            args=(devices, stop_flag, _ogn_reconnect),
            daemon=True, name="ogn-thread",
        )
        t.start()
        threads.append(t)
        print(f"  [monitor] OGN thread started — {len(ogn_keys)} callsigns")

    if pt_keys:
        t = threading.Thread(
            target=pt_poll_loop,
            args=(devices, stop_flag),
            daemon=True, name="pt-thread",
        )
        t.start()
        threads.append(t)
        print(f"  [monitor] PT thread started — {len(pt_keys)} slugs")

    t = threading.Thread(
        target=bot_thread,
        args=(devices, stop_flag),
        daemon=True, name="bot-thread",
    )
    t.start()
    threads.append(t)

    t = threading.Thread(
        target=_timeout_loop,
        args=(devices, stop_flag),
        daemon=True, name="timeout-thread",
    )
    t.start()
    threads.append(t)

    print(f"  [monitor] ready — {len(devices)} device keys, {len(threads)} threads")
    return threads
