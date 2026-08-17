from datetime import datetime, timezone
from typing import List

import httpx

import db as _db
from core.beacon import Beacon, parse_pt_beacon
from core.config import PT_API_LIVE, PT_POLL_SEC
from core.emergency import get_config
from core.notify import notify
from core.state_machine import update_device
from core.terrain import compute_agl


def fetch_pt_beacons() -> List[Beacon]:
    try:
        r = httpx.get(PT_API_LIVE, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:
        print(f"  [PT] fetch error: {e}")
        return []
    return [b for entry in data if (b := parse_pt_beacon(entry))]


def pt_poll_loop(devices: dict, stop_flag) -> None:
    print(f"  [PT] starting — polling every {PT_POLL_SEC}s")
    while not stop_flag.is_set():
        beacons = fetch_pt_beacons()
        now     = datetime.now(timezone.utc)
        cfg     = get_config()
        for beacon in beacons:
            beacon.agl_m = compute_agl(beacon)
            dev = devices.get(beacon.device_id)
            if dev is None:
                continue
            if dev.ogn_is_fresh(now, cfg):
                continue
            _db.write_beacon(beacon)
            events = update_device(dev, beacon, cfg)
            _db.set_device_state(beacon.name, dev.state.name)
            if events:
                notify(events)
            else:
                print(f"[{beacon.ts.strftime('%H:%M:%S')}][ PT] {beacon.name}: "
                      f"alt={beacon.alt_m:.0f}m  speed={beacon.speed_kmh:.0f}km/h  "
                      f"vspeed={beacon.vspeed_ms:+.1f}m/s  {dev.state.name}")
        stop_flag.wait(PT_POLL_SEC)
