from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ogn.parser import parse, AprsParseError

# Populated at startup by core.monitor._build_index()
callsign_to_name: dict[str, str] = {}
pt_slug_to_name:  dict[str, str] = {}
# Push sources (GrappaSafe and anything else speaking the same contract):
# ingest token -> display name.
gs_token_to_name: dict[str, str] = {}

@dataclass
class Beacon:
    device_id:  str
    name:       str
    source:     str        # "ogn" | "puretrack"
    ts:         datetime
    lat:        float
    lon:        float
    alt_m:      float
    speed_kmh:  float = 0.0
    course_deg: float = 0.0
    vspeed_ms:  float = 0.0
    agl_m:      float = 0.0
    # Only push sources carry these: the GrappaSafe app forwards the peak
    # acceleration since its last fix (impact watch) and the GPS accuracy
    # (so a bad fix can be kept out of the immobility check). Radio beacons
    # have neither, hence None.
    accel_g:    Optional[float] = None
    accuracy_m: Optional[float] = None
    raw:        str   = field(default="", repr=False)

    @property
    def maps_url(self) -> str:
        return f"https://maps.google.com/?q={self.lat:.5f},{self.lon:.5f}"


def parse_ogn_beacon(raw: str) -> Optional[Beacon]:
    if not raw or raw.startswith("#"):
        return None
    try:
        pkt = parse(raw)
    except (AprsParseError, Exception):
        return None
    if not isinstance(pkt, dict):
        return None
    callsign = pkt.get("name", "")
    if not callsign or callsign not in callsign_to_name:
        return None
    if pkt.get("latitude") is None or pkt.get("longitude") is None:
        return None
    ts = pkt.get("timestamp") or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return Beacon(
        device_id  = callsign,
        name       = callsign_to_name[callsign],
        source     = "ogn",
        ts         = ts,
        lat        = float(pkt.get("latitude",     0.0) or 0.0),
        lon        = float(pkt.get("longitude",    0.0) or 0.0),
        alt_m      = float(pkt.get("altitude",     0.0) or 0.0),
        speed_kmh  = float(pkt.get("ground_speed", 0.0) or 0.0),
        course_deg = float(pkt.get("track",        0.0) or 0.0),
        vspeed_ms  = float(pkt.get("climb_rate",   0.0) or 0.0),
        raw        = raw,
    )


def _parse_pt_fields(entry: str) -> dict:
    fields = {}
    for token in entry.split(","):
        if not token:
            continue
        key = token[0]
        val = token[1:] if len(token) > 1 else ""
        if key not in fields:
            fields[key] = val
    return fields


def parse_pt_beacon(entry: str) -> Optional[Beacon]:
    f    = _parse_pt_fields(entry)
    slug = f.get("j", "")
    if slug not in pt_slug_to_name:
        return None
    if "T" not in f or "L" not in f or "G" not in f:
        return None
    try:
        ts  = datetime.fromtimestamp(int(f["T"]), tz=timezone.utc)
        lat = float(f["L"])
        lon = float(f["G"])
        alt = float(f.get("A", 0) or 0)
        spd = float(f.get("S", 0) or 0) * 3.6   # m/s → km/h
        vs  = float(f.get("V", 0) or 0)
        crs = float(f.get("C", 0) or 0)
    except (ValueError, KeyError):
        return None
    return Beacon(
        device_id  = f"PT_{slug}",
        name       = pt_slug_to_name[slug],
        source     = "puretrack",
        ts         = ts,
        lat        = lat,
        lon        = lon,
        alt_m      = alt,
        speed_kmh  = spd,
        course_deg = crs,
        vspeed_ms  = vs,
        raw        = entry,
    )


def parse_gs_beacon(payload: dict, token: str) -> Optional[Beacon]:
    """
    Beacon from a push source (POST /api/ingest). The sender is authenticated by
    its token, which is what resolves the device: nothing in the body decides
    whose position this is.

    Altitude is AMSL, like every other source; AGL is computed by the caller.
    """
    if token not in gs_token_to_name:
        return None
    try:
        lat = float(payload["lat"])
        lon = float(payload["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None

    raw_ts = payload.get("ts")
    ts = None
    if raw_ts:
        try:
            ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        except ValueError:
            ts = None
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    def _num(key: str) -> float:
        try:
            return float(payload.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _opt(key: str) -> Optional[float]:
        v = payload.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return Beacon(
        device_id  = f"GS_{token}",
        name       = gs_token_to_name[token],
        source     = str(payload.get("source") or "grappasafe")[:32],
        ts         = ts,
        lat        = lat,
        lon        = lon,
        alt_m      = _num("alt_m"),
        speed_kmh  = _num("speed_kmh"),
        course_deg = _num("course_deg"),
        vspeed_ms  = _num("vspeed_ms"),
        accel_g    = _opt("accel_g"),
        accuracy_m = _opt("accuracy_m"),
    )
