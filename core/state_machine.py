"""
Flight state machine.

    UNKNOWN -> GROUNDED <-> WALKING -> AIRBORNE -> GROUNDED
    any state -> SIGNAL_LOST -> back to where it was

Transitions are confirmed over TIME, not over a number of beacons: the sources
tick at very different rates (FANET ~2s, GrappaSafe push 15s, PureTrack ~30s),
so a "two beacons" confirmation used to mean four seconds on one source and a
minute on another. Every threshold comes from EmConfig, which is loaded from the
config table and editable by an admin.

The machine also drives the two safety nets in core/emergency.py — the reserve
watch and, for sources that carry an accelerometer, the impact watch.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional

from core.beacon import Beacon
from core.emergency import (
    DEFAULT_CONFIG, EmConfig, chute_step, impact_step,
)


class State(Enum):
    UNKNOWN     = auto()
    GROUNDED    = auto()
    WALKING     = auto()
    AIRBORNE    = auto()
    SIGNAL_LOST = auto()


class EventKind(Enum):
    TAKEOFF         = "takeoff"
    LANDING         = "landing"
    BAD_AIR         = "bad_air"
    BAD_LANDING     = "bad_landing"
    RESERVE         = "reserve"
    IMPACT          = "impact"
    IN_ORBITA       = "in_orbita"
    PIANGE_GIALLO   = "piange_giallo"
    HA_FATTO_STRADA = "ha_fatto_strada"
    CLIMBING_WELL   = "climbing_well"
    SIGNAL_LOST     = "signal_lost"
    SIGNAL_FOUND    = "signal_found"


@dataclass
class Event:
    kind:   EventKind
    beacon: Beacon
    note:   str = ""


@dataclass
class DeviceState:
    device_id:    str
    name:         str
    state:        State               = State.UNKNOWN
    last_beacon:  Optional[Beacon]    = None
    last_seen:    Optional[datetime]  = None
    last_ogn_seen: Optional[datetime] = None

    # Confirmation timestamps: set when a condition first holds, cleared when it
    # breaks, when the transition fires, or after a gap in the data.
    takeoff_since:     Optional[datetime] = None
    landing_since:     Optional[datetime] = None
    emerg_since:       Optional[datetime] = None
    bad_landing_since: Optional[datetime] = None
    rapid_descent_seen: bool = False

    # Where the device was before the signal was lost, so it comes back to the
    # right state instead of dropping to GROUNDED — which used to fake a second
    # takeoff, move the takeoff point and re-arm every milestone.
    state_before_lost: Optional[State] = None
    lost_announced:    bool            = False

    # flight info
    airborne_since: Optional[datetime] = None
    takeoff_lat:    Optional[float]    = None
    takeoff_lon:    Optional[float]    = None

    # milestone flags — reset per takeoff
    notified_in_orbita:       bool               = False
    notified_piange_giallo:   bool               = False
    notified_ha_fatto_strada: bool               = False
    lift_streak_since:        Optional[datetime] = None
    notified_climbing_well:   bool               = False

    # Recent positions (ts, lat, lon, accuracy_m) for displacement-based
    # immobility. Accuracy is None for sources that do not report it (OGN).
    recent: list = field(default_factory=list)

    # Reserve watch (core/emergency.py owns the logic, the state lives here).
    chute_watch:         bool               = False
    chute_fired:         bool               = False
    chute_arm_since:     Optional[datetime] = None
    chute_recover_since: Optional[datetime] = None
    chute_last_agl:      Optional[float]    = None

    # Impact watch (accelerometer sources only).
    impact_at:    Optional[datetime] = None
    impact_lat:   Optional[float]    = None
    impact_lon:   Optional[float]    = None
    impact_fired: bool               = False

    def ogn_is_fresh(self, now: datetime, cfg: EmConfig = DEFAULT_CONFIG) -> bool:
        if self.last_ogn_seen is None:
            return False
        return (now - self.last_ogn_seen).total_seconds() < cfg.ogn_primary_s


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R  = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _reset_streaks(dev: DeviceState) -> None:
    """Clear the confirmations in progress after a gap in the data. A stale
    condition must not be allowed to fire a transition."""
    dev.takeoff_since = None
    dev.landing_since = None
    dev.emerg_since = None
    dev.bad_landing_since = None
    dev.rapid_descent_seen = False
    dev.lift_streak_since = None


def _held(since: Optional[datetime], now: datetime, seconds: float) -> bool:
    return since is not None and (now - since).total_seconds() >= seconds


def _arm_takeoff(dev: DeviceState, beacon: Beacon, now: datetime) -> None:
    dev.state          = State.AIRBORNE
    dev.airborne_since = now
    dev.takeoff_lat    = beacon.lat
    dev.takeoff_lon    = beacon.lon
    dev.takeoff_since  = None
    dev.landing_since  = None
    dev.notified_in_orbita       = False
    dev.notified_piange_giallo   = False
    dev.notified_ha_fatto_strada = False


def update_device(dev: DeviceState, beacon: Beacon,
                  cfg: EmConfig = DEFAULT_CONFIG) -> List[Event]:
    events: List[Event] = []

    now = beacon.ts
    gap_s = (now - dev.last_seen).total_seconds() if dev.last_seen else None

    dev.last_beacon = beacon
    dev.last_seen   = now
    if beacon.source == "ogn":
        dev.last_ogn_seen = now

    if gap_s is not None and gap_s > cfg.max_gap_s:
        _reset_streaks(dev)

    speed  = beacon.speed_kmh
    vspeed = beacon.vspeed_ms
    agl    = beacon.agl_m

    # Position buffer for the immobility checks. Long enough to cover the
    # widest window either watch asks for.
    horizon = max(cfg.chute_immobile_s, cfg.impact_immobile_s)
    dev.recent.append((now, beacon.lat, beacon.lon, beacon.accuracy_m))
    dev.recent = [p for p in dev.recent if (now - p[0]).total_seconds() <= horizon]

    # ── BAD LANDING (any state) ───────────────────────────────────────────────
    if vspeed <= cfg.bad_landing_vspeed_ms:
        dev.rapid_descent_seen = True
        dev.bad_landing_since = None
    elif dev.rapid_descent_seen:
        if abs(vspeed) < 1.0 and speed < 5.0 and agl <= cfg.landing_alt_m:
            if dev.bad_landing_since is None:
                dev.bad_landing_since = now
            elif _held(dev.bad_landing_since, now, cfg.bad_landing_confirm_s):
                dev.rapid_descent_seen = False
                dev.bad_landing_since = None
                events.append(Event(EventKind.BAD_LANDING, beacon, note=f"AGL={agl:.0f}m"))
        else:
            dev.rapid_descent_seen = False
            dev.bad_landing_since = None
    else:
        dev.bad_landing_since = None

    # ── BAD AIR: steep sink, still flying (informational) ────────────────────
    # The real reserve net is the watch below; this stays as the "rough air"
    # notification it has always been.
    if dev.state == State.AIRBORNE:
        if (agl > cfg.airborne_alt_m and vspeed <= cfg.emerg_vspeed_ms
                and speed <= cfg.emerg_speed_kmh):
            if dev.emerg_since is None:
                dev.emerg_since = now
            elif _held(dev.emerg_since, now, cfg.emerg_confirm_s):
                dev.emerg_since = None
                events.append(Event(EventKind.BAD_AIR, beacon,
                                    note=f"vspeed={vspeed:.1f}m/s  AGL={agl:.0f}m"))
        else:
            dev.emerg_since = None

    # ── SIGNAL_LOST: recovery ────────────────────────────────────────────────
    # Back to the state the device was in, not down to GROUNDED. A pilot who
    # reappears at 2000 m is still flying, and the old behaviour turned that
    # into a fake takeoff, a wrong takeoff point and a second round of
    # milestone notifications.
    if dev.state == State.SIGNAL_LOST:
        dev.state = dev.state_before_lost or (
            State.AIRBORNE if agl > cfg.airborne_alt_m else State.GROUNDED
        )
        dev.state_before_lost = None
        if dev.lost_announced:
            events.append(Event(EventKind.SIGNAL_FOUND, beacon))
        dev.lost_announced = False

    # ── UNKNOWN: initialise ──────────────────────────────────────────────────
    # First sight already in the air is not a takeoff: no event here.
    if dev.state == State.UNKNOWN:
        if agl > cfg.airborne_alt_m or speed >= cfg.takeoff_speed_kmh:
            dev.state          = State.AIRBORNE
            dev.airborne_since = now
        else:
            dev.state = State.GROUNDED

    # ── GROUNDED / WALKING → AIRBORNE ────────────────────────────────────────
    if dev.state in (State.GROUNDED, State.WALKING):
        if agl <= cfg.landing_alt_m:
            dev.state = State.WALKING if speed >= cfg.walking_speed_kmh else State.GROUNDED

        if agl > cfg.airborne_alt_m:
            # Unambiguous: airborne now, no confirmation needed.
            _arm_takeoff(dev, beacon, now)
            events.append(Event(EventKind.TAKEOFF, beacon,
                                note=f"AGL={agl:.0f}m  speed={speed:.0f}km/h"))
        elif speed >= cfg.takeoff_speed_kmh:
            if dev.takeoff_since is None:
                dev.takeoff_since = now
            elif _held(dev.takeoff_since, now, cfg.takeoff_confirm_s):
                _arm_takeoff(dev, beacon, now)
                events.append(Event(EventKind.TAKEOFF, beacon,
                                    note=f"AGL={agl:.0f}m  speed={speed:.0f}km/h"))
        else:
            dev.takeoff_since = None

    # ── AIRBORNE: landing check + milestones ─────────────────────────────────
    elif dev.state == State.AIRBORNE:
        # lift tracking for CLIMBING_WELL
        if vspeed >= cfg.lift_vspeed_ms:
            if dev.lift_streak_since is None:
                dev.lift_streak_since = now
        else:
            dev.lift_streak_since      = None
            dev.notified_climbing_well = False

        if agl > cfg.airborne_alt_m:
            dev.landing_since = None
        elif agl <= cfg.landing_alt_m and speed <= cfg.landing_speed_kmh:
            if dev.landing_since is None:
                dev.landing_since = now
        else:
            dev.landing_since = None

        if _held(dev.landing_since, now, cfg.landing_confirm_s):
            dur = ""
            if dev.airborne_since:
                secs = (now - dev.airborne_since).total_seconds()
                dur  = f"durata ~{int(secs // 60)} min"
            dev.state                  = State.GROUNDED
            dev.landing_since          = None
            dev.lift_streak_since      = None
            dev.notified_climbing_well = False
            events.append(Event(EventKind.LANDING, beacon, note=dur))

        # milestones only while still airborne
        if dev.state == State.AIRBORNE:
            if (not dev.notified_climbing_well
                    and _held(dev.lift_streak_since, now, cfg.lift_confirm_s)):
                dev.notified_climbing_well = True
                events.append(Event(EventKind.CLIMBING_WELL, beacon,
                                    note=f"+{vspeed:.1f}m/s  AGL={agl:.0f}m"))

            if not dev.notified_in_orbita and agl >= cfg.orbit_alt_m:
                dev.notified_in_orbita = True
                events.append(Event(EventKind.IN_ORBITA, beacon, note=f"{agl:.0f}m AGL"))

            if not dev.notified_piange_giallo and dev.airborne_since:
                if (now - dev.airborne_since).total_seconds() >= cfg.long_flight_h * 3600:
                    dev.notified_piange_giallo = True
                    h = (now - dev.airborne_since).total_seconds() / 3600
                    events.append(Event(EventKind.PIANGE_GIALLO, beacon,
                                        note=f"{h:.1f}h in volo"))

            if not dev.notified_ha_fatto_strada and dev.takeoff_lat is not None:
                dist = haversine_km(dev.takeoff_lat, dev.takeoff_lon, beacon.lat, beacon.lon)
                if dist >= cfg.distance_km:
                    dev.notified_ha_fatto_strada = True
                    events.append(Event(EventKind.HA_FATTO_STRADA, beacon,
                                        note=f"{dist:.0f}km dal decollo"))

    # ── Safety nets ──────────────────────────────────────────────────────────
    # After the SM, so the reserve watch sees the state this beacon produced.
    if chute_step(dev, cfg, now,
                  airborne=(dev.state == State.AIRBORNE),
                  agl_m=agl, speed_kmh=speed, vspeed_ms=vspeed, gap_s=gap_s):
        events.append(Event(EventKind.RESERVE, beacon,
                            note=f"discesa a rateo-riserva, poi fermo — AGL={agl:.0f}m"))

    if impact_step(dev, cfg, now, beacon.accel_g, beacon.lat, beacon.lon):
        events.append(Event(EventKind.IMPACT, beacon,
                            note=f"impatto, poi fermo — AGL={agl:.0f}m"))

    return events


def check_timeouts(devices: dict, now: datetime,
                   cfg: EmConfig = DEFAULT_CONFIG) -> List[Event]:
    """Silence sweep. Two things happen here: the reserve watch's Path 2 (a
    descent that ended in silence near the ground) and the ordinary
    SIGNAL_LOST.

    A device that goes quiet while GROUNDED is almost always an instrument
    switched off after landing, so the transition happens without notifying
    anyone — and so does the recovery, later. Only a device lost *in flight* is
    worth telling a watchlist about.
    """
    from core.emergency import chute_signal_lost

    events: List[Event] = []
    seen: set = set()
    for dev in devices.values():
        if id(dev) in seen:
            continue
        seen.add(id(dev))

        # Path 2 first: it can fire well before the signal-lost timeout, and it
        # is the louder of the two.
        if chute_signal_lost(dev, cfg, now) and dev.last_beacon is not None:
            dev.chute_fired = True
            elapsed = (now - dev.last_seen).total_seconds()
            events.append(Event(EventKind.RESERVE, dev.last_beacon,
                                note=f"discesa a rateo-riserva, poi silenzio a "
                                     f"{dev.chute_last_agl:.0f}m AGL "
                                     f"({int(elapsed)}s fa)"))

        if dev.state in (State.GROUNDED, State.WALKING, State.AIRBORNE) and dev.last_seen:
            elapsed = (now - dev.last_seen).total_seconds()
            if elapsed >= cfg.signal_lost_min * 60:
                was = dev.state
                dev.state             = State.SIGNAL_LOST
                dev.state_before_lost = was
                # Announce only a pilot lost in flight, and not when the reserve
                # alarm already said it louder.
                announce = was == State.AIRBORNE and not dev.chute_fired
                dev.lost_announced = announce
                if announce and dev.last_beacon is not None:
                    events.append(Event(EventKind.SIGNAL_LOST, dev.last_beacon,
                                        note=f"ultimo beacon {int(elapsed // 60)} min fa"))
    return events
