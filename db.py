import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WEBAPP_DB = Path(os.getenv("WEBAPP_DB", "webapp.db"))

ALWAYS_ON_EVENTS = {"takeoff", "landing", "bad_air", "bad_landing", "reserve", "impact"}
ALL_EVENTS = [
    ("takeoff",         True),
    ("landing",         True),
    ("bad_air",         True),
    ("bad_landing",     True),
    ("reserve",         True),
    ("impact",          True),
    ("climbing_well",   False),
    ("in_orbita",       False),
    ("piange_giallo",   False),
    ("ha_fatto_strada", False),
    ("signal_lost",     False),
    ("signal_found",    False),
]


def _conn(db_path=None):
    con = sqlite3.connect(db_path or WEBAPP_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'pilot',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS watchlists (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL,
            telegram_chat_id TEXT,
            language         TEXT NOT NULL DEFAULT 'en',
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS watchlist_members (
            watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role         TEXT NOT NULL DEFAULT 'pilot',
            PRIMARY KEY (watchlist_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS devices (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name  TEXT NOT NULL,
            sources       TEXT NOT NULL DEFAULT '{}',
            color         TEXT NOT NULL DEFAULT '#4a9eff',
            owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS notification_prefs (
            watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
            event_key    TEXT NOT NULL,
            enabled      INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (watchlist_id, event_key)
        );

        CREATE TABLE IF NOT EXISTS beacons (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  TEXT NOT NULL,
            name       TEXT NOT NULL,
            source     TEXT NOT NULL,
            ts         TEXT NOT NULL,
            lat        REAL,
            lon        REAL,
            alt_m      REAL,
            agl_m      REAL,
            speed_kmh  REAL,
            vspeed_ms  REAL,
            course_deg REAL
        );

        CREATE INDEX IF NOT EXISTS beacons_name_ts ON beacons (name, ts DESC);

        CREATE TABLE IF NOT EXISTS device_states (
            name       TEXT PRIMARY KEY,
            state      TEXT NOT NULL DEFAULT 'UNKNOWN',
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Thresholds of the state machine and of the two safety nets, editable
        -- from the admin page. They used to be environment variables, which
        -- meant rebuilding the image to change a number: the only way to tune
        -- these is against real flights, so they have to move at runtime.
        CREATE TABLE IF NOT EXISTS config (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            categoria   TEXT NOT NULL DEFAULT 'volo',
            descrizione TEXT NOT NULL DEFAULT '',
            aggiornato  TEXT DEFAULT (datetime('now'))
        );
    """)
    con.close()

    _seed_config()

    # Migrations for existing deployments
    for stmt in [
        "ALTER TABLE devices ADD COLUMN color TEXT NOT NULL DEFAULT '#4a9eff'",
        "ALTER TABLE users ADD COLUMN first_name TEXT",
        "ALTER TABLE users ADD COLUMN last_name TEXT",
        "ALTER TABLE users ADD COLUMN email TEXT",
        "ALTER TABLE users ADD COLUMN emergency_phone TEXT",
    ]:
        try:
            con = _conn()
            con.execute(stmt)
            con.commit()
            con.close()
        except Exception:
            pass


# ── config (SM + safety-net thresholds) ───────────────────────────────────────

def _seed_config() -> None:
    """Insert the defaults that are missing and realign the metadata on every
    start: the admin's value survives, a re-described or re-categorised
    parameter does not stay stale. Retired keys are dropped."""
    from core.config import LEGACY_SEED
    from core.emergency import CONFIG_META, RETIRED_CONFIG_KEYS, EmConfig

    defaults = EmConfig()
    con = _conn()
    for key, categoria, descrizione in CONFIG_META:
        # A value the deployment had set in .env before the table existed wins
        # over the dataclass default — but only when seeding the row.
        seed = LEGACY_SEED.get(key)
        try:
            value = str(float(seed)) if seed is not None else str(getattr(defaults, key))
        except (TypeError, ValueError):
            value = str(getattr(defaults, key))
        con.execute(
            "INSERT OR IGNORE INTO config (key, value, categoria, descrizione) "
            "VALUES (?,?,?,?)",
            (key, value, categoria, descrizione),
        )
        con.execute(
            "UPDATE config SET categoria=?, descrizione=? WHERE key=?",
            (categoria, descrizione, key),
        )
    for key in RETIRED_CONFIG_KEYS:
        con.execute("DELETE FROM config WHERE key=?", (key,))
    con.commit()
    con.close()


def get_config_rows() -> list:
    con = _conn()
    rows = con.execute(
        "SELECT key, value, categoria, descrizione, aggiornato FROM config "
        "ORDER BY categoria, key"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def load_config():
    """Build an EmConfig from the table. A missing or unreadable row falls back
    to the dataclass default, so a broken value can never take the machine
    down."""
    from core.emergency import EmConfig

    cfg = EmConfig()
    try:
        con = _conn()
        rows = con.execute("SELECT key, value FROM config").fetchall()
        con.close()
    except Exception as e:
        print(f"  [config] load error, using defaults: {e}")
        return cfg
    for row in rows:
        if not hasattr(cfg, row["key"]):
            continue
        try:
            setattr(cfg, row["key"], float(row["value"]))
        except (TypeError, ValueError):
            pass
    return cfg


def set_config_value(key: str, value: float) -> None:
    con = _conn()
    con.execute(
        "UPDATE config SET value=?, aggiornato=datetime('now') WHERE key=?",
        (str(value), key),
    )
    con.commit()
    con.close()


# ── device states ─────────────────────────────────────────────────────────────

def set_device_state(name: str, state: str) -> None:
    con = _conn()
    con.execute(
        "INSERT INTO device_states (name, state, updated_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(name) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
        (name, state),
    )
    con.commit()
    con.close()


def get_last_beacon_for_name(name: str) -> dict | None:
    """Return the most recent beacon row for a device name, or None."""
    con = _conn()
    row = con.execute(
        "SELECT * FROM beacons WHERE name = ? ORDER BY ts DESC LIMIT 1",
        (name,),
    ).fetchone()
    con.close()
    return dict(row) if row else None


# ── beacons ────────────────────────────────────────────────────────────────────

def write_beacon(beacon) -> None:
    con = _conn()
    con.execute(
        "INSERT INTO beacons "
        "(device_id, name, source, ts, lat, lon, alt_m, agl_m, speed_kmh, vspeed_ms, course_deg) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            beacon.device_id, beacon.name, beacon.source,
            beacon.ts.isoformat(),
            beacon.lat, beacon.lon,
            beacon.alt_m, beacon.agl_m,
            beacon.speed_kmh, beacon.vspeed_ms, beacon.course_deg,
        ),
    )
    con.commit()
    con.close()


# ── users ──────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id: int):
    con = _conn()
    row = con.execute(
        "SELECT id, username, role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_all_users():
    con = _conn()
    rows = con.execute(
        "SELECT id, username, role, created_at, first_name, last_name, email, emergency_phone "
        "FROM users ORDER BY username"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_user_profile(uid: int):
    con = _conn()
    row = con.execute(
        "SELECT id, username, role, created_at, first_name, last_name, email, emergency_phone "
        "FROM users WHERE id=?", (uid,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def update_own_profile(uid: int, first_name: str, last_name: str, email: str, emergency_phone: str):
    con = _conn()
    con.execute(
        "UPDATE users SET first_name=?, last_name=?, email=?, emergency_phone=? WHERE id=?",
        (first_name or None, last_name or None, email or None, emergency_phone or None, uid),
    )
    con.commit()
    con.close()


def update_user_profile(uid: int, first_name: str, last_name: str, email: str, emergency_phone: str, role: str):
    con = _conn()
    con.execute(
        "UPDATE users SET first_name=?, last_name=?, email=?, emergency_phone=?, role=? WHERE id=?",
        (first_name or None, last_name or None, email or None, emergency_phone or None, role, uid),
    )
    con.commit()
    con.close()


def create_user(username: str, password_hash: str, role: str = "pilot") -> int:
    con = _conn()
    cur = con.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    con.commit()
    uid = cur.lastrowid
    con.close()
    return uid


def update_user_password(user_id: int, password_hash: str):
    con = _conn()
    con.execute(
        "UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id)
    )
    con.commit()
    con.close()


# ── watchlists ─────────────────────────────────────────────────────────────────

def get_watchlists():
    con = _conn()
    rows = con.execute(
        "SELECT id, name FROM watchlists ORDER BY name"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_all_watchlists():
    con = _conn()
    rows = con.execute(
        "SELECT id, name, telegram_chat_id, language FROM watchlists ORDER BY name"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_user_watchlists(user_id: int):
    con = _conn()
    rows = con.execute(
        "SELECT w.id, w.name, w.language, wm.role "
        "FROM watchlists w JOIN watchlist_members wm ON w.id=wm.watchlist_id "
        "WHERE wm.user_id=? ORDER BY w.name",
        (user_id,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_watchlist(name: str, telegram_chat_id: str = None, language: str = "en") -> int:
    con = _conn()
    cur = con.execute(
        "INSERT INTO watchlists (name, telegram_chat_id, language) VALUES (?, ?, ?)",
        (name, telegram_chat_id, language),
    )
    con.commit()
    wid = cur.lastrowid
    con.close()
    return wid


def delete_watchlist(watchlist_id: int):
    con = _conn()
    con.execute("DELETE FROM watchlists WHERE id=?", (watchlist_id,))
    con.commit()
    con.close()


def update_watchlist_settings(watchlist_id: int, telegram_chat_id: str, language: str):
    con = _conn()
    con.execute(
        "UPDATE watchlists SET telegram_chat_id=?, language=? WHERE id=?",
        (telegram_chat_id, language, watchlist_id),
    )
    con.commit()
    con.close()


def update_watchlist_language(watchlist_id: int, language: str):
    con = _conn()
    con.execute(
        "UPDATE watchlists SET language=? WHERE id=?",
        (language, watchlist_id),
    )
    con.commit()
    con.close()


def get_watchlist_by_chat_id(chat_id: str):
    con = _conn()
    row = con.execute(
        "SELECT id, name, telegram_chat_id, language FROM watchlists "
        "WHERE telegram_chat_id=?",
        (chat_id,),
    ).fetchone()
    con.close()
    return dict(row) if row else None


# ── watchlist members ──────────────────────────────────────────────────────────

def get_watchlist_members(watchlist_id: int):
    con = _conn()
    rows = con.execute(
        "SELECT u.id, u.username, u.role as global_role, wm.role as watchlist_role "
        "FROM users u JOIN watchlist_members wm ON u.id=wm.user_id "
        "WHERE wm.watchlist_id=? ORDER BY u.username",
        (watchlist_id,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_watchlist_member(watchlist_id: int, user_id: int, role: str = "pilot"):
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO watchlist_members (watchlist_id, user_id, role) "
        "VALUES (?, ?, ?)",
        (watchlist_id, user_id, role),
    )
    con.commit()
    con.close()


def remove_watchlist_member(watchlist_id: int, user_id: int):
    con = _conn()
    con.execute(
        "DELETE FROM watchlist_members WHERE watchlist_id=? AND user_id=?",
        (watchlist_id, user_id),
    )
    con.commit()
    con.close()


# ── devices ────────────────────────────────────────────────────────────────────

def _parse_sources(rows):
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"])
        result.append(d)
    return result


def get_user_devices(user_id: int):
    con = _conn()
    rows = con.execute(
        "SELECT id, display_name, sources, color FROM devices "
        "WHERE owner_user_id=? ORDER BY display_name",
        (user_id,),
    ).fetchall()
    con.close()
    return _parse_sources(rows)


def get_all_devices():
    con = _conn()
    rows = con.execute(
        "SELECT d.id, d.display_name, d.sources, u.username as owner "
        "FROM devices d LEFT JOIN users u ON d.owner_user_id=u.id "
        "ORDER BY d.display_name"
    ).fetchall()
    con.close()
    return _parse_sources(rows)


def get_all_watched_devices() -> list:
    """All devices whose owner is a member of at least one watchlist."""
    con = _conn()
    rows = con.execute(
        "SELECT DISTINCT d.id, d.display_name, d.sources "
        "FROM devices d "
        "JOIN watchlist_members wm ON d.owner_user_id = wm.user_id"
    ).fetchall()
    con.close()
    return _parse_sources(rows)


def add_device(user_id: int, display_name: str, sources: dict, color: str = "#4a9eff") -> int:
    con = _conn()
    cur = con.execute(
        "INSERT INTO devices (display_name, sources, color, owner_user_id) VALUES (?, ?, ?, ?)",
        (display_name, json.dumps(sources), color, user_id),
    )
    con.commit()
    did = cur.lastrowid
    con.close()
    return did


def update_device(device_id: int, owner_user_id: int, display_name: str, sources: dict, color: str = "#4a9eff"):
    con = _conn()
    con.execute(
        "UPDATE devices SET display_name=?, sources=?, color=? WHERE id=? AND owner_user_id=?",
        (display_name, json.dumps(sources), color, device_id, owner_user_id),
    )
    con.commit()
    con.close()


def update_device_admin(device_id: int, display_name: str, sources: dict):
    con = _conn()
    con.execute(
        "UPDATE devices SET display_name=?, sources=? WHERE id=?",
        (display_name, json.dumps(sources), device_id),
    )
    con.commit()
    con.close()


def delete_user(uid: int) -> None:
    """Delete a user and all their devices. watchlist_members cascade automatically."""
    con = _conn()
    con.execute("DELETE FROM devices WHERE owner_user_id=?", (uid,))
    con.execute("DELETE FROM users WHERE id=?", (uid,))
    con.commit()
    con.close()


def delete_device(device_id: int, owner_user_id: int):
    con = _conn()
    con.execute(
        "DELETE FROM devices WHERE id=? AND owner_user_id=?",
        (device_id, owner_user_id),
    )
    con.commit()
    con.close()


def get_watchlist_devices(watchlist_id: int) -> list:
    """Devices in a watchlist via member ownership."""
    con = _conn()
    rows = con.execute(
        "SELECT d.id, d.display_name as name, d.display_name, d.sources, u.username as owner "
        "FROM devices d "
        "JOIN users u ON d.owner_user_id = u.id "
        "JOIN watchlist_members wm ON wm.user_id = u.id "
        "WHERE wm.watchlist_id = ? "
        "ORDER BY d.display_name",
        (watchlist_id,),
    ).fetchall()
    con.close()
    return _parse_sources(rows)


# ── pilot positions (from beacons table) ──────────────────────────────────────

def _infer_state(row: dict, age_s: float) -> str:
    if age_s > 600:
        return "SIGNAL_LOST"
    if row.get("agl_m") and row["agl_m"] > 50:
        return "AIRBORNE"
    if row.get("speed_kmh") and row["speed_kmh"] > 20:
        return "AIRBORNE"
    return "GROUNDED"


def get_pilot_positions(watchlist_id: int) -> list:
    con = _conn()
    name_rows = con.execute(
        "SELECT DISTINCT d.display_name, d.color "
        "FROM devices d "
        "JOIN watchlist_members wm ON d.owner_user_id = wm.user_id "
        "WHERE wm.watchlist_id = ? "
        "ORDER BY d.display_name",
        (watchlist_id,),
    ).fetchall()
    names       = [r["display_name"] for r in name_rows]
    name_colors = {r["display_name"]: r["color"] for r in name_rows}

    if not names:
        con.close()
        return []

    placeholders = ",".join("?" * len(names))
    beacon_rows = con.execute(
        f"SELECT b.name, b.lat, b.lon, b.alt_m, b.agl_m, b.speed_kmh, b.vspeed_ms, b.course_deg, b.ts, "
        f"       ds.state as stored_state "
        f"FROM beacons b "
        f"LEFT JOIN device_states ds ON ds.name = b.name "
        f"WHERE b.name IN ({placeholders}) "
        f"AND b.ts = (SELECT MAX(b2.ts) FROM beacons b2 WHERE b2.name = b.name)",
        names,
    ).fetchall()
    con.close()

    found = {r["name"]: dict(r) for r in beacon_rows}
    now   = datetime.now(timezone.utc)
    result = []

    for name in names:
        color = name_colors.get(name, "#4a9eff")
        if name in found:
            r = found[name]
            r["color"] = color
            stored_state = r.pop("stored_state", None)
            try:
                ts = datetime.fromisoformat(r["ts"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_s      = (now - ts).total_seconds()
                r["age_s"] = int(age_s)
                # age > 10 min always wins: stale stored_state must not hide signal-loss
                if age_s > 600:
                    r["state"] = "SIGNAL_LOST"
                else:
                    r["state"] = stored_state if stored_state else _infer_state(r, age_s)
            except Exception:
                r["age_s"] = None
                r["state"] = stored_state or "UNKNOWN"
        else:
            r = {
                "name": name, "lat": None, "lon": None,
                "state": "UNKNOWN", "age_s": None, "color": color,
                "alt_m": None, "agl_m": None, "speed_kmh": None, "vspeed_ms": None,
            }
        result.append(r)

    return result


def get_pilot_positions_multi(watchlist_ids=None) -> list:
    """Pilot positions for the given watchlist IDs, or all watched pilots if None/[]."""
    con = _conn()
    if watchlist_ids:
        ph = ",".join("?" * len(watchlist_ids))
        name_rows = con.execute(
            f"SELECT DISTINCT d.display_name, d.color "
            f"FROM devices d "
            f"JOIN watchlist_members wm ON d.owner_user_id = wm.user_id "
            f"WHERE wm.watchlist_id IN ({ph}) "
            f"ORDER BY d.display_name",
            watchlist_ids,
        ).fetchall()
    else:
        name_rows = con.execute(
            "SELECT DISTINCT d.display_name, d.color "
            "FROM devices d "
            "JOIN watchlist_members wm ON d.owner_user_id = wm.user_id "
            "ORDER BY d.display_name"
        ).fetchall()

    names       = [r["display_name"] for r in name_rows]
    name_colors = {r["display_name"]: r["color"] for r in name_rows}

    if not names:
        con.close()
        return []

    ph = ",".join("?" * len(names))
    beacon_rows = con.execute(
        f"SELECT b.name, b.lat, b.lon, b.alt_m, b.agl_m, b.speed_kmh, b.vspeed_ms, b.course_deg, b.ts, "
        f"       ds.state as stored_state "
        f"FROM beacons b "
        f"LEFT JOIN device_states ds ON ds.name = b.name "
        f"WHERE b.name IN ({ph}) "
        f"AND b.ts = (SELECT MAX(b2.ts) FROM beacons b2 WHERE b2.name = b.name)",
        names,
    ).fetchall()
    con.close()

    found = {r["name"]: dict(r) for r in beacon_rows}
    now   = datetime.now(timezone.utc)
    result = []

    for name in names:
        color = name_colors.get(name, "#4a9eff")
        if name in found:
            r = found[name]
            r["color"] = color
            stored_state = r.pop("stored_state", None)
            try:
                ts = datetime.fromisoformat(r["ts"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_s      = (now - ts).total_seconds()
                r["age_s"] = int(age_s)
                # age > 10 min always wins: stale stored_state must not hide signal-loss
                if age_s > 600:
                    r["state"] = "SIGNAL_LOST"
                else:
                    r["state"] = stored_state if stored_state else _infer_state(r, age_s)
            except Exception:
                r["age_s"] = None
                r["state"] = stored_state or "UNKNOWN"
        else:
            r = {
                "name": name, "lat": None, "lon": None,
                "state": "UNKNOWN", "age_s": None, "color": color,
                "alt_m": None, "agl_m": None, "speed_kmh": None, "vspeed_ms": None,
            }
        result.append(r)

    return result


# ── pilot track ───────────────────────────────────────────────────────────────

def get_pilot_track(name: str, cfg=None) -> list:
    """The pilot's current (or last) flight, as a list of points.

    Not "the last N beacons": with FANET at ~2s a hundred beacons are three
    minutes of flight, with PureTrack at ~30s they are nearly an hour — the same
    line meaning different things depending on the receiver. The track is cut by
    TIME instead: walking back from the newest beacon until a silence longer
    than track_gap_min, which is what separates one flight from the previous
    one.

    Returns [] when the last beacon is older than track_keep_min, so a track
    stays on the map for a while after landing and then goes away on its own.
    Long flights are thinned to track_max_points: a four-hour FANET flight is
    seven thousand points, and a polyline redrawn every few seconds cannot carry
    them (nor would the eye tell the difference).
    """
    if cfg is None:
        from core.emergency import get_config
        cfg = get_config()

    con = _conn()
    rows = con.execute(
        "SELECT ts, lat, lon FROM beacons WHERE name=? AND lat IS NOT NULL "
        "ORDER BY ts DESC LIMIT 20000",
        (name,),
    ).fetchall()
    con.close()
    if not rows:
        return []

    def _ts(value):
        try:
            t = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

    newest = _ts(rows[0]["ts"])
    if newest is None:
        return []
    now = datetime.now(timezone.utc)
    if (now - newest).total_seconds() > cfg.track_keep_min * 60:
        return []

    gap_s = cfg.track_gap_min * 60
    flight = [rows[0]]
    prev = newest
    for row in rows[1:]:
        t = _ts(row["ts"])
        if t is None:
            continue
        if (prev - t).total_seconds() > gap_s:
            break
        flight.append(row)
        prev = t

    flight.reverse()
    cap = int(cfg.track_max_points)
    if cap > 2 and len(flight) > cap:
        step = len(flight) / cap
        thinned = [flight[int(i * step)] for i in range(cap - 1)]
        thinned.append(flight[-1])       # never drop the current position
        flight = thinned

    return [{"lat": r["lat"], "lon": r["lon"]} for r in flight]


# ── notify helpers ─────────────────────────────────────────────────────────────

def get_watchlists_for_device_name(display_name: str) -> list:
    """All watchlists that contain a user who owns a device with this display_name."""
    con = _conn()
    rows = con.execute(
        "SELECT DISTINCT w.id, w.telegram_chat_id, w.language "
        "FROM watchlists w "
        "JOIN watchlist_members wm ON w.id = wm.watchlist_id "
        "JOIN devices d ON d.owner_user_id = wm.user_id "
        "WHERE d.display_name = ?",
        (display_name,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── notification prefs ─────────────────────────────────────────────────────────

def get_notification_prefs(watchlist_id: int) -> list:
    con = _conn()
    stored = {
        r["event_key"]: bool(r["enabled"])
        for r in con.execute(
            "SELECT event_key, enabled FROM notification_prefs WHERE watchlist_id=?",
            (watchlist_id,),
        ).fetchall()
    }
    con.close()
    return [
        {"event_key": key, "always_on": always_on, "enabled": stored.get(key, True)}
        for key, always_on in ALL_EVENTS
    ]


def set_notification_pref(watchlist_id: int, event_key: str, enabled: bool):
    if event_key in ALWAYS_ON_EVENTS:
        return
    con = _conn()
    con.execute(
        "INSERT INTO notification_prefs (watchlist_id, event_key, enabled) VALUES (?, ?, ?) "
        "ON CONFLICT(watchlist_id, event_key) DO UPDATE SET enabled=excluded.enabled",
        (watchlist_id, event_key, int(enabled)),
    )
    con.commit()
    con.close()


def is_event_enabled_wl(watchlist_id: int, event_key: str) -> bool:
    if event_key in ALWAYS_ON_EVENTS:
        return True
    con = _conn()
    row = con.execute(
        "SELECT enabled FROM notification_prefs WHERE watchlist_id=? AND event_key=?",
        (watchlist_id, event_key),
    ).fetchone()
    con.close()
    return bool(row["enabled"]) if row else True
