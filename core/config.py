import os
from dotenv import load_dotenv

load_dotenv()


def aprs_passcode(callsign: str) -> int:
    call = callsign.upper().split("-")[0]
    code = 0x73E2
    for i, c in enumerate(call):
        if i % 2 == 0:
            code ^= ord(c) << 8
        else:
            code ^= ord(c)
    return code & 0x7FFF


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

APRS_USER = os.getenv("APRS_USER", "OE1FW")
APRS_PASS = aprs_passcode(APRS_USER)

# Detection thresholds now live in the config table and are edited from the
# admin page (core/emergency.py:EmConfig). These environment variables survive
# for one purpose only: seeding a database that has never had the table, so a
# deployment that overrode a value in .env keeps it instead of silently
# reverting to the default. Once seeded, the DB is the only source of truth.
#
# The *_CONFIRM_N counters have no successor: confirmations moved from counting
# beacons to counting seconds, which is the whole point of the change.
LEGACY_SEED = {
    "takeoff_speed_kmh": os.getenv("TAKEOFF_SPEED_KMH"),
    "landing_speed_kmh": os.getenv("LANDING_SPEED_KMH"),
    "signal_lost_min":   os.getenv("SIGNAL_LOST_MIN"),
    "emerg_vspeed_ms":   os.getenv("EMERG_VSPEED_MS"),
    "emerg_speed_kmh":   os.getenv("EMERG_SPEED_KMH"),
    "ogn_primary_s":     os.getenv("OGN_PRIMARY_SEC"),
}

PT_POLL_SEC = int(os.getenv("PT_POLL_SEC", "30"))
PT_API_LIVE = os.getenv("PT_API_LIVE", "https://puretrack.io/api/live")

TILE_DIR = os.getenv("TILE_DIR", "/app/srtm_tiles")

OGN_PREFIXES = {
    "fanet":      "FNT",
    "flarm":      "FLR",
    "ogntracker": "OGN",
    "naviter":    "NAV",
    "icao":       "ICA",
}
