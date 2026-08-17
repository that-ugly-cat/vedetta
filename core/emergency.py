"""
Thresholds and the two safety nets, ported from GrappaSafe.

The state machine describes what a pilot is doing; this module holds the
parameters it works with and the two detectors that decide something has gone
wrong:

  * the reserve-chute watch — arms on a sustained reserve-rate descent and
    fires when the descent *terminates* (immobility, or a beacon lost near the
    ground) rather than *recovers* into normal flight;
  * the impact watch — for sources that carry an accelerometer peak (the
    GrappaSafe app, pushed to /api/ingest): a hard hit followed by immobility.

Every threshold lives in the config table and is editable from the admin page,
because the only way to tune these is against real flights.

No import from core.state_machine: the detectors take plain values, so the two
modules stay independent (and the code stays close to GrappaSafe's, which is
where fixes will keep coming from).
"""

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EmConfig:
    """SM + detector parameters, loaded from the config table at runtime."""

    # ── Flight state machine ──────────────────────────────────────────────
    # Confirmations are in SECONDS, not in beacons. Sources tick at wildly
    # different rates (FANET ~2s, GrappaSafe 15s, PureTrack ~30s): counting
    # beacons made the same threshold mean four seconds on one source and a
    # minute on another.
    takeoff_speed_kmh:    float = 20.0
    takeoff_confirm_s:    float = 20.0
    airborne_alt_m:       float = 150.0  # AGL above which flight is certain:
    #   go AIRBORNE at once, with no confirmation. A gappy OGN feed keeps
    #   resetting the streak, which otherwise leaves a pilot at altitude
    #   pinned to GROUNDED.
    landing_speed_kmh:    float = 10.0
    landing_alt_m:        float = 50.0   # AGL
    landing_confirm_s:    float = 45.0
    walking_speed_kmh:    float = 5.0    # on the ground, above this = WALKING

    # Silence longer than this clears the confirmations in progress: two
    # beacons twenty minutes apart are not a streak.
    max_gap_s:            float = 180.0

    # ── Informational events ──────────────────────────────────────────────
    emerg_vspeed_ms:      float = -8.0   # rough air (steep sink, still flying)
    emerg_speed_kmh:      float = 20.0
    emerg_confirm_s:      float = 8.0
    bad_landing_vspeed_ms: float = -6.0  # fast descent, then an abrupt stop
    bad_landing_confirm_s: float = 8.0

    # ── Reserve-chute watch ───────────────────────────────────────────────
    # A reserve canopy comes down at ~5-6 m/s: below the rough-air threshold,
    # which is why -8 m/s never sees one. What tells a reserve from a spiral
    # or a B-stall is not the rate, it is how it ends.
    chute_arm_vspeed_ms:     float = -5.0
    chute_recover_vspeed_ms: float = -2.0
    chute_confirm_s:         float = 12.0   # to arm, and to recover
    chute_immobile_s:        float = 120.0  # Path 1: immobile this long -> fire
    descending_max_speed_kmh: float = 50.0  # horizontal cap: excludes aircraft
    signal_lost_wait_s:      float = 120.0  # Path 2: silence after the descent
    signal_lost_floor_agl_m: float = 50.0   # last AGL must be this low to alarm

    # ── Impact watch (accelerometer sources only) ─────────────────────────
    impact_g:             float = 10.0   # peak g (0 disables); a normal landing
    #   is ~1-3 g. Only the GrappaSafe app carries this: OGN has no such signal.
    impact_immobile_s:    float = 120.0  # immobile after the hit -> fire

    # Immobility is measured as displacement over a window, never as
    # instantaneous speed: GPS speed jitters and would keep resetting the clock.
    immobile_radius_m:    float = 60.0
    gps_accuracy_max_m:   float = 100.0  # worse fixes are ignored for immobility

    # ── Signal / sources ──────────────────────────────────────────────────
    signal_lost_min:      float = 10.0   # minutes of silence -> SIGNAL_LOST
    ogn_primary_s:        float = 90.0   # OGN wins over other sources this long

    # ── Tracks on the map ─────────────────────────────────────────────────
    track_gap_min:        float = 30.0   # silence that separates two flights
    track_keep_min:       float = 120.0  # a track stays visible this long after
    #   the last beacon, so a flight does not vanish the moment the pilot lands
    track_max_points:     float = 800.0  # thinning cap: a 4h FANET flight is
    #   ~7000 points, which no polyline redrawn every few seconds can carry

    # ── Milestones ────────────────────────────────────────────────────────
    orbit_alt_m:          float = 1500.0  # AGL -> "in orbita"
    long_flight_h:        float = 4.0     # hours airborne -> "piange giallo"
    distance_km:          float = 30.0    # from takeoff -> "ha fatto strada"
    lift_vspeed_ms:       float = 3.0     # climbing this well...
    lift_confirm_s:       float = 120.0   # ...for this long -> "climbing well"


DEFAULT_CONFIG = EmConfig()


# (key, category, description) — the description is what the admin reads.
CONFIG_META = [
    ("takeoff_speed_kmh",    "volo", "Velocità minima per il decollo (km/h)"),
    ("takeoff_confirm_s",    "volo", "Secondi in condizione di decollo per confermarlo"),
    ("airborne_alt_m",       "volo", "Quota AGL oltre cui si è certamente in volo (AIRBORNE subito)"),
    ("landing_speed_kmh",    "volo", "Velocità massima per l'atterraggio (km/h)"),
    ("landing_alt_m",        "volo", "Quota AGL massima per l'atterraggio (m)"),
    ("landing_confirm_s",    "volo", "Secondi in condizione di atterraggio per confermarlo"),
    ("walking_speed_kmh",    "volo", "Velocità sopra cui, a terra, il pilota cammina (km/h)"),
    ("max_gap_s",            "volo", "Silenzio oltre cui le conferme in corso si azzerano (s)"),

    ("emerg_vspeed_ms",      "eventi", "Velocità verticale per 'aria brutta' (m/s, negativo)"),
    ("emerg_speed_kmh",      "eventi", "Velocità orizzontale massima per 'aria brutta' (km/h)"),
    ("emerg_confirm_s",      "eventi", "Secondi in aria brutta per notificare"),
    ("bad_landing_vspeed_ms", "eventi", "Velocità verticale che precede un atterraggio duro (m/s)"),
    ("bad_landing_confirm_s", "eventi", "Secondi di arresto brusco per confermare l'atterraggio duro"),

    ("chute_arm_vspeed_ms",     "riserva", "Rateo di discesa che arma la vigilanza riserva (m/s, negativo)"),
    ("chute_recover_vspeed_ms", "riserva", "Rateo sopra cui la discesa è rientrata in volo (m/s, negativo)"),
    ("chute_confirm_s",         "riserva", "Secondi a rateo-riserva per armare (e per rientrare)"),
    ("chute_immobile_s",        "riserva", "Secondi immobile dopo la discesa → allarme riserva"),
    ("descending_max_speed_kmh", "riserva", "Velocità orizzontale massima per la discesa (esclude aeromobili)"),
    ("signal_lost_wait_s",      "riserva", "Secondi di silenzio dopo la discesa prima di allarmare"),
    ("signal_lost_floor_agl_m", "riserva", "Quota AGL massima alla perdita segnale per allarmare (m)"),

    ("impact_g",             "impatto", "Picco accelerometro che conta come impatto (g, 0 = disattivato)"),
    ("impact_immobile_s",    "impatto", "Secondi immobile dopo l'impatto → allarme"),
    ("immobile_radius_m",    "impatto", "Raggio entro cui si è considerati fermi (m)"),
    ("gps_accuracy_max_m",   "impatto", "Accuratezza GPS oltre cui il punto è ignorato (m)"),

    ("signal_lost_min",      "sistema", "Minuti di silenzio prima di dichiarare il segnale perso"),
    ("ogn_primary_s",        "sistema", "Secondi in cui un beacon OGN ha la precedenza sulle altre sorgenti"),

    ("track_gap_min",        "tracce", "Minuti di silenzio che separano due voli nella traccia"),
    ("track_keep_min",       "tracce", "Minuti in cui la traccia resta visibile dopo l'ultimo beacon"),
    ("track_max_points",     "tracce", "Punti massimi per traccia (oltre, viene diradata)"),

    ("orbit_alt_m",          "milestone", "Quota AGL per 'in orbita' (m)"),
    ("long_flight_h",        "milestone", "Ore di volo per 'piange giallo'"),
    ("distance_km",          "milestone", "Distanza dal decollo per 'ha fatto strada' (km)"),
    ("lift_vspeed_ms",       "milestone", "Salita minima per 'in buon lift' (m/s)"),
    ("lift_confirm_s",       "milestone", "Secondi di salita per 'in buon lift'"),
]

CONFIG_CATEGORIES = ["volo", "eventi", "riserva", "impatto", "sistema", "tracce", "milestone"]

# Keys that existed once and must be dropped from the table on seed, so they do
# not linger as dead editable rows.
RETIRED_CONFIG_KEYS: list = []


# ── runtime config, with a short cache ────────────────────────────────────────
# Every worker asks for the config on every beacon, so it cannot hit the DB each
# time; a 60s TTL means an edit on the admin page is live within a minute,
# without a restart. Lives here, not in monitor.py, so the workers can import it
# without an import cycle.

_cfg: Optional[EmConfig] = None
_cfg_expires: float = 0.0
_cfg_lock = threading.Lock()
_CFG_TTL_S = 60.0


def get_config() -> EmConfig:
    global _cfg, _cfg_expires
    with _cfg_lock:
        now = time.monotonic()
        if _cfg is None or now >= _cfg_expires:
            import db as _db
            _cfg = _db.load_config()
            _cfg_expires = now + _CFG_TTL_S
        return _cfg


def invalidate_config() -> None:
    """Drop the cache after an admin edit, so the change is live at once."""
    global _cfg_expires
    with _cfg_lock:
        _cfg_expires = 0.0


# ── geometry / immobility ─────────────────────────────────────────────────────

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def is_immobile(recent, window_s: float, cfg: EmConfig, now: datetime) -> bool:
    """True if the pilot stayed within immobile_radius_m over the last window_s.

    Displacement over a window, not instantaneous speed. Needs history covering
    most of the window: with two fixes ten seconds apart we cannot yet claim two
    minutes of immobility.

    Outlier-tolerant, because a single bogus fix must not mask a real one: the
    centre is the component-wise median and a small share of points may fall
    outside the radius. In GrappaSafe field testing one cell-tower fix 3.6 km
    off suppressed a genuine post-impact alarm.
    """
    pts = [(t, la, lo) for (t, la, lo, acc) in recent
           if (now - t).total_seconds() <= window_s
           and (acc is None or acc <= cfg.gps_accuracy_max_m)]
    if len(pts) < 2:
        return False
    oldest = min(t for t, _, _ in pts)
    if (now - oldest).total_seconds() < window_s * 0.8:
        return False
    lats = sorted(la for _, la, _ in pts)
    lons = sorted(lo for _, _, lo in pts)
    med_la = lats[len(lats) // 2]
    med_lo = lons[len(lons) // 2]
    outliers = sum(1 for _, la, lo in pts
                   if haversine_m(med_la, med_lo, la, lo) > cfg.immobile_radius_m)
    allowed = max(1, len(pts) // 8) if len(pts) >= 4 else 0
    return outliers <= allowed


def _last_good(recent, cfg: EmConfig, n: int):
    """Last n (lat, lon) with usable accuracy, newest last."""
    good = [(la, lo) for (t, la, lo, acc) in recent
            if acc is None or acc <= cfg.gps_accuracy_max_m]
    return good[-n:]


# ── reserve-chute watch ───────────────────────────────────────────────────────

def chute_step(dev, cfg: EmConfig, now: datetime, airborne: bool,
               agl_m: Optional[float], speed_kmh: float, vspeed_ms: float,
               gap_s: Optional[float] = None) -> bool:
    """Feed one beacon into the reserve watch. True if Path 1 fires here.

    Arms on a descent at or below chute_arm_vspeed_ms — horizontal speed under
    the aircraft cap, and only for a device that actually took off — sustained
    for chute_confirm_s. Disarms only on a genuine recovery: vertical speed back
    up AND still moving at flight speed. Both conditions matter: a pilot down
    and immobile also has vspeed ~0, and reading that as a recovery would mean
    Path 1 never fires.
    """
    # A long gap kills the streaks in progress but never disarms an active
    # watch: the silence itself is what Path 2 listens for.
    if gap_s is not None and gap_s > cfg.max_gap_s:
        dev.chute_arm_since = None
        dev.chute_recover_since = None

    if agl_m is not None:
        dev.chute_last_agl = agl_m

    descending = (vspeed_ms <= cfg.chute_arm_vspeed_ms
                  and speed_kmh <= cfg.descending_max_speed_kmh)

    if not dev.chute_watch:
        if descending and airborne:
            if dev.chute_arm_since is None:
                dev.chute_arm_since = now
            elif (now - dev.chute_arm_since).total_seconds() >= cfg.chute_confirm_s:
                dev.chute_watch = True
                dev.chute_fired = False       # fresh episode
                dev.chute_arm_since = None
        else:
            dev.chute_arm_since = None
        return False

    # Armed. Recovery to normal flight ends the episode.
    if vspeed_ms >= cfg.chute_recover_vspeed_ms and speed_kmh >= cfg.takeoff_speed_kmh:
        if dev.chute_recover_since is None:
            dev.chute_recover_since = now
        elif (now - dev.chute_recover_since).total_seconds() >= cfg.chute_confirm_s:
            dev.chute_watch = False
            dev.chute_fired = False
            dev.chute_recover_since = None
            return False
    else:
        dev.chute_recover_since = None

    # Path 1: immobile inside the radius (on the ground, or hanging in a tree).
    if not dev.chute_fired and is_immobile(dev.recent, cfg.chute_immobile_s, cfg, now):
        dev.chute_fired = True
        return True
    return False


def chute_signal_lost(dev, cfg: EmConfig, now: datetime) -> bool:
    """Path 2: an armed watch whose beacon went quiet near the ground.

    Above signal_lost_floor_agl_m the silence is indistinguishable from a
    coverage hole, so it does not alarm: an accepted miss, deliberately.
    """
    if not dev.chute_watch or dev.chute_fired:
        return False
    if dev.last_seen is None:
        return False
    if (now - dev.last_seen).total_seconds() < cfg.signal_lost_wait_s:
        return False
    agl = dev.chute_last_agl
    return agl is not None and agl <= cfg.signal_lost_floor_agl_m


# ── impact watch (accelerometer sources) ──────────────────────────────────────

def impact_step(dev, cfg: EmConfig, now: datetime, accel_g: Optional[float],
                lat: Optional[float], lon: Optional[float]) -> bool:
    """Feed one beacon into the impact watch. True if the alarm fires here.

    Only sources that carry an accelerometer peak reach this: the GrappaSafe app
    forwards the peak g since its last fix. A hit alone means nothing (a hard
    landing is still a landing) — it takes a hit followed by immobility.
    """
    if cfg.impact_g <= 0:
        return False

    if accel_g is not None and accel_g >= cfg.impact_g:
        dev.impact_at = now
        dev.impact_lat, dev.impact_lon = lat, lon
        dev.impact_fired = False

    if dev.impact_at is None or dev.impact_fired:
        return False

    # Walked away = evidently fine. Two consecutive far fixes, not one: a lone
    # cell-tower fix can teleport kilometres and would wipe a real impact.
    if dev.impact_lat is not None:
        last2 = _last_good(dev.recent, cfg, 2)
        if len(last2) == 2 and all(
            haversine_m(dev.impact_lat, dev.impact_lon, la, lo) > cfg.immobile_radius_m
            for la, lo in last2
        ):
            dev.impact_at = dev.impact_lat = dev.impact_lon = None
            return False

    if ((now - dev.impact_at).total_seconds() >= cfg.impact_immobile_s
            and is_immobile(dev.recent, cfg.impact_immobile_s, cfg, now)):
        dev.impact_fired = True
        return True
    return False
