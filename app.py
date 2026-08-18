import json
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from auth import hash_password, verify_password, get_current_user
from translations import TRANSLATIONS, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from core.beacon import gs_token_to_name, parse_gs_beacon
from core.emergency import get_config, invalidate_config
from core.monitor import start_monitor, get_devices, refresh_devices
from core.notify import notify
from core.state_machine import update_device as sm_update_device
from core.terrain import compute_agl
from db import (
    init_db,
    get_watchlists, get_all_watchlists, get_user_watchlists,
    create_watchlist, update_watchlist_settings, delete_watchlist,
    get_pilot_positions, get_pilot_positions_multi,
    get_all_users, create_user, get_user_profile, update_user_password,
    update_own_profile, update_user_profile, delete_user,
    get_user_devices, add_device, update_device, delete_device,
    get_all_devices, update_device_admin,
    get_pilot_track,
    get_watchlist_devices,
    get_watchlist_members, add_watchlist_member, remove_watchlist_member,
    get_notification_prefs, set_notification_pref,
    write_beacon, set_device_state,
    get_config_rows, set_config_value,
    _conn,
)

SECRET_KEY  = os.getenv("SECRET_KEY", "change-me-in-production")
_stop_flag  = threading.Event()

init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_monitor(_stop_flag)
    yield
    _stop_flag.set()


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_lang(request: Request) -> str:
    lang = request.cookies.get("lang", DEFAULT_LANGUAGE)
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

def _require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse("/", status_code=303)
    return user, None


def _require_admin(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return None, JSONResponse({"error": "forbidden"}, status_code=403)
    return user, None


# ── HTML routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if get_current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    lang = _get_lang(request)
    return templates.TemplateResponse(request, "index.html", {
        "watchlists": get_watchlists(),
        "t": TRANSLATIONS[lang],
        "lang": lang,
        "t_json": json.dumps(TRANSLATIONS[lang], ensure_ascii=False),
    })


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    con = _conn()
    row = con.execute(
        "SELECT id, password_hash, role FROM users WHERE username=?", (username,)
    ).fetchone()
    con.close()

    if row and verify_password(password, row["password_hash"]):
        request.session["user"] = {"id": row["id"], "username": username, "role": row["role"]}
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(request, "index.html", {
        "watchlists": get_watchlists(),
        "error": "Credenziali non valide.",
    }, status_code=401)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user, redir = _require_auth(request)
    if redir:
        return redir
    lang = _get_lang(request)
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "watchlists": get_user_watchlists(user["id"]),
        "t": TRANSLATIONS[lang],
        "lang": lang,
        "t_json": json.dumps(TRANSLATIONS[lang], ensure_ascii=False),
    })


# ── auth API ──────────────────────────────────────────────────────────────────

@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    con = _conn()
    row = con.execute(
        "SELECT id, password_hash, role FROM users WHERE username=?", (username,)
    ).fetchone()
    con.close()
    if row and verify_password(password, row["password_hash"]):
        request.session["user"] = {"id": row["id"], "username": username, "role": row["role"]}
        return {"ok": True}
    return JSONResponse({"error": "Credenziali non valide."}, status_code=401)


@app.post("/api/register")
async def api_register(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or len(password) < 6:
        return JSONResponse({"error": "Username e password (min 6 caratteri) obbligatori."}, status_code=400)
    try:
        uid = create_user(username, hash_password(password), "pilot")
        update_own_profile(
            uid,
            body.get("first_name", ""),
            body.get("last_name", ""),
            body.get("email", ""),
            body.get("emergency_phone", ""),
        )
        request.session["user"] = {"id": uid, "username": username, "role": "pilot"}
        return {"ok": True}
    except Exception:
        return JSONResponse({"error": "Username già in uso."}, status_code=409)


# ── public API ────────────────────────────────────────────────────────────────

@app.get("/api/watchlists")
async def api_watchlists():
    return get_watchlists()


@app.get("/api/pilots")
async def api_all_pilots(wl: str = ""):
    ids = [int(x) for x in wl.split(",") if x.strip().isdigit()] if wl else []
    return get_pilot_positions_multi(ids if ids else None)


@app.get("/api/pilots/{name}/track")
async def api_pilot_track(name: str):
    """The pilot's current or last flight. Cut by time, not by beacon count —
    see db.get_pilot_track — and empty once the flight is old enough."""
    return get_pilot_track(name, get_config())


@app.get("/api/watchlist/{wid}/pilots")
async def api_pilots(wid: int):
    return get_pilot_positions(wid)


# ── pilot API (auth required) ─────────────────────────────────────────────────

@app.get("/api/me")
async def api_me(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return get_user_profile(user["id"]) or user


@app.put("/api/me/profile")
async def api_update_my_profile(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    update_own_profile(
        user["id"],
        body.get("first_name", ""),
        body.get("last_name", ""),
        body.get("email", ""),
        body.get("emergency_phone", ""),
    )
    return {"ok": True}


@app.put("/api/me/password")
async def api_change_my_password(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    con = _conn()
    row = con.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    con.close()
    if not row or not verify_password(body.get("current_password", ""), row["password_hash"]):
        return JSONResponse({"error": "Password attuale non corretta."}, status_code=400)
    new_pwd = body.get("new_password", "")
    if len(new_pwd) < 6:
        return JSONResponse({"error": "Nuova password troppo corta (min 6 caratteri)."}, status_code=400)
    update_user_password(user["id"], hash_password(new_pwd))
    return {"ok": True}


@app.get("/api/me/devices")
async def api_my_devices(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return get_user_devices(user["id"])


@app.post("/api/me/devices")
async def api_add_device(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    did = add_device(user["id"], body["display_name"], body.get("sources", {}), body.get("color", "#4a9eff"))
    return {"id": did}


@app.put("/api/me/devices/{device_id}")
async def api_update_device(request: Request, device_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    update_device(device_id, user["id"], body["display_name"], body.get("sources", {}), body.get("color", "#4a9eff"))
    return {"ok": True}


@app.delete("/api/me/devices/{device_id}")
async def api_delete_device(request: Request, device_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    delete_device(device_id, user["id"])
    return {"ok": True}


@app.get("/api/me/watchlists")
async def api_my_watchlists(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return get_user_watchlists(user["id"])


# ── admin API ─────────────────────────────────────────────────────────────────

@app.get("/api/admin/watchlists")
async def api_admin_watchlists(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    return get_all_watchlists()


@app.post("/api/admin/watchlists")
async def api_create_watchlist(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    wid = create_watchlist(body["name"], body.get("telegram_chat_id"), body.get("language", "en"))
    return {"id": wid}


@app.delete("/api/admin/watchlists/{wid}")
async def api_delete_watchlist(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    delete_watchlist(wid)
    return {"ok": True}


@app.put("/api/admin/watchlists/{wid}/settings")
async def api_watchlist_settings(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    update_watchlist_settings(wid, body.get("telegram_chat_id"), body.get("language", "en"))
    return {"ok": True}


@app.get("/api/admin/watchlists/{wid}/members")
async def api_members(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    return get_watchlist_members(wid)


@app.post("/api/admin/watchlists/{wid}/members")
async def api_add_member(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    add_watchlist_member(wid, body["user_id"], body.get("role", "pilot"))
    return {"ok": True}


@app.delete("/api/admin/watchlists/{wid}/members/{uid}")
async def api_remove_member(request: Request, wid: int, uid: int):
    _, err = _require_admin(request)
    if err:
        return err
    remove_watchlist_member(wid, uid)
    return {"ok": True}


@app.get("/api/admin/watchlists/{wid}/devices")
async def api_watchlist_devices(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    return get_watchlist_devices(wid)


# ── self-service join / leave ─────────────────────────────────────────────────

@app.post("/api/watchlists/{wid}/join")
async def api_join_watchlist(request: Request, wid: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    add_watchlist_member(wid, user["id"])
    return {"ok": True}


@app.delete("/api/watchlists/{wid}/leave")
async def api_leave_watchlist(request: Request, wid: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    remove_watchlist_member(wid, user["id"])
    return {"ok": True}


@app.get("/api/admin/watchlists/{wid}/notifications")
async def api_notifications(request: Request, wid: int):
    _, err = _require_admin(request)
    if err:
        return err
    return get_notification_prefs(wid)


@app.put("/api/admin/watchlists/{wid}/notifications/{event_key}")
async def api_set_notification(request: Request, wid: int, event_key: str):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    set_notification_pref(wid, event_key, body["enabled"])
    return {"ok": True}


@app.get("/api/admin/users")
async def api_users(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    return get_all_users()


@app.post("/api/admin/users")
async def api_create_user(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    uid = create_user(body["username"], hash_password(body["password"]), body.get("role", "pilot"))
    return {"id": uid}


@app.delete("/api/admin/users/{uid}")
async def api_delete_user(request: Request, uid: int):
    user, err = _require_admin(request)
    if err:
        return err
    if user["id"] == uid:
        return JSONResponse({"error": "Non puoi eliminare te stesso."}, status_code=400)
    delete_user(uid)
    return {"ok": True}


@app.put("/api/admin/users/{uid}/password")
async def api_reset_password(request: Request, uid: int):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    update_user_password(uid, hash_password(body["password"]))
    return {"ok": True}


@app.put("/api/admin/users/{uid}/profile")
async def api_update_user_profile(request: Request, uid: int):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    update_user_profile(
        uid,
        body.get("first_name", ""),
        body.get("last_name", ""),
        body.get("email", ""),
        body.get("emergency_phone", ""),
        body.get("role", "pilot"),
    )
    return {"ok": True}


@app.get("/api/admin/devices")
async def api_all_devices(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    return get_all_devices()


@app.put("/api/admin/devices/{did}")
async def api_update_device_admin(request: Request, did: int):
    _, err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    update_device_admin(did, body["display_name"], body.get("sources", {}))
    return {"ok": True}


# ── admin: thresholds ─────────────────────────────────────────────────────────

@app.get("/api/admin/config")
async def api_get_config(request: Request):
    _, err = _require_admin(request)
    if err:
        return err
    return get_config_rows()


@app.put("/api/admin/config/{key}")
async def api_set_config(request: Request, key: str):
    _, err = _require_admin(request)
    if err:
        return err
    from core.emergency import EmConfig
    if not hasattr(EmConfig(), key):
        return JSONResponse({"error": "unknown key"}, status_code=404)
    body = await request.json()
    try:
        value = float(body["value"])
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"error": "value must be a number"}, status_code=400)
    set_config_value(key, value)
    invalidate_config()   # live at once, not at the next TTL tick
    return {"ok": True, "key": key, "value": value}


# ── ingest (push sources) ─────────────────────────────────────────────────────
#
# Sources that cannot be polled push their positions here instead: GrappaSafe
# forwards the fixes of the pilots who opted in, and anything else speaking the
# same contract works too. The token identifies the device — nothing in the body
# decides whose position this is — and is stored as the "grappasafe" source of
# that device, so revoking it is just editing the device.


@app.get("/api/me/ingest-token")
async def api_ingest_token(request: Request):
    """A fresh token to paste into the sending app. Only generated here: it is
    stored when the user saves the device."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return {"token": secrets.token_urlsafe(18)}


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return ""


def _handle_ingest(token: str, payload: dict) -> tuple:
    if token not in gs_token_to_name:
        # Freshly created token: rebuild the index instead of making the pilot
        # wait for the next hot-reload tick.
        refresh_devices()
    if token not in gs_token_to_name:
        return 403, {"error": "unknown token"}

    # Handshake from the sender ("is this token wired to the right pilot?"):
    # it carries no position and must not touch the map.
    if payload.get("test"):
        return 200, {"ok": True, "test": True, "name": gs_token_to_name[token]}

    beacon = parse_gs_beacon(payload, token)
    if beacon is None:
        return 400, {"error": "invalid payload"}

    dev = get_devices().get(f"GS_{token}")
    if dev is None:
        return 503, {"error": "device not indexed yet"}

    now = datetime.now(timezone.utc)
    cfg = get_config()
    # OGN wins while it is fresh, exactly as for PureTrack: a pilot carrying a
    # FLARM keeps the clean radio vspeed instead of a phone's GPS estimate.
    # The accelerometer peak is the exception the app brings and the radio does
    # not have — but it only matters together with the positions it comes with,
    # so it follows the same precedence.
    if dev.ogn_is_fresh(now, cfg):
        return 200, {"ok": True, "skipped": "ogn_primary"}

    # The state machine assumes monotonic timestamps. A sender draining its
    # offline queue replays old fixes: they must not walk the pilot backwards.
    last = dev.last_seen
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if beacon.ts <= last:
            return 200, {"ok": True, "skipped": "stale"}

    beacon.agl_m = compute_agl(beacon)
    write_beacon(beacon)
    events = sm_update_device(dev, beacon, cfg)
    set_device_state(beacon.name, dev.state.name)
    if events:
        notify(events)
    return 200, {"ok": True, "name": beacon.name, "state": dev.state.name}


@app.post("/api/ingest")
async def api_ingest(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid json"}, status_code=400)

    token = _bearer_token(request) or str(payload.get("token") or "")
    if not token:
        return JSONResponse({"error": "missing token"}, status_code=401)

    # Off the event loop: the DB writes are blocking and notify() talks to
    # Telegram, which on a slow round trip would stall every other request.
    status, body = await run_in_threadpool(_handle_ingest, token, payload)
    return JSONResponse(body, status_code=status)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
