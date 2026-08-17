from datetime import datetime, timezone

import httpx

import db as _db
from core.config import TELEGRAM_TOKEN
from core.state_machine import DeviceState, State
from messages import DEFAULT_LANGUAGE, MESSAGES, SUPPORTED_LANGUAGES

_STATE_ICON = {
    State.AIRBORNE:    "✈️",   # ✈️
    State.GROUNDED:    "\U0001f6ec",      # 🛬
    State.WALKING:     "\U0001f6b6",      # 🚶
    State.SIGNAL_LOST: "\U0001f4f5",      # 📵
    State.UNKNOWN:     "❓",          # ❓
}


def _state_icon(state: State) -> str:
    return _STATE_ICON.get(state, "❓")


def _unique_devices(devices: dict) -> list:
    seen, result = set(), []
    for dev in devices.values():
        if id(dev) not in seen:
            seen.add(id(dev))
            result.append(dev)
    return result


def _devices_for_watchlist(all_devices: dict, watchlist_id: int) -> dict:
    """Return the subset of all_devices belonging to this watchlist."""
    wl_rows = _db.get_watchlist_devices(watchlist_id)
    names   = {row["display_name"] for row in wl_rows}
    return {k: v for k, v in all_devices.items() if v.name in names}


def _fmt_age(age_s: int, lang: str = DEFAULT_LANGUAGE) -> str:
    if age_s < 3600:
        m, s = divmod(age_s, 60)
        return f"{m}m {s}s fa" if lang == "it" else f"{m}m {s}s ago"
    elif age_s < 86400:
        h, rem = divmod(age_s, 3600)
        m = rem // 60
        return f"{h}h {m}m fa" if lang == "it" else f"{h}h {m}m ago"
    else:
        d, rem = divmod(age_s, 86400)
        h = rem // 3600
        suf = "fa" if lang == "it" else "ago"
        unit_d = "g" if lang == "it" else "d"
        return f"{d}{unit_d} {h}h {suf}"


def _format_summary(devices: dict, lang: str = DEFAULT_LANGUAGE) -> str:
    msgs = MESSAGES.get(lang, MESSAGES[DEFAULT_LANGUAGE])
    lines = [msgs["status_header"], ""]

    _order = {State.AIRBORNE: 0, State.GROUNDED: 1, State.WALKING: 1,
              State.SIGNAL_LOST: 2, State.UNKNOWN: 3}
    devs = sorted(_unique_devices(devices), key=lambda d: (_order.get(d.state, 3), d.name))

    unknown_sep_added = False
    for dev in devs:
        if dev.state == State.UNKNOWN and not unknown_sep_added:
            unknown_sep_added = True
            lines.append("—")

        icon = _state_icon(dev.state)

        if dev.state == State.UNKNOWN or dev.last_beacon is None:
            lines.append(f"❓ *{dev.name}* — {msgs['no_data']}")
            continue

        b = dev.last_beacon
        age_s = (datetime.now(timezone.utc) - b.ts).total_seconds()

        if dev.state == State.SIGNAL_LOST:
            if lang == "it":
                age_str = f"ultimo segnale {int(age_s // 60)}min fa"
            else:
                age_str = f"last seen {int(age_s // 60)}min ago"
            lines.append(f"📵 *{dev.name}* · {age_str}")
            continue

        age_label = (msgs["age_live"] if age_s <= 90
                     else msgs["age_min"].format(min=int(age_s // 60)))

        if dev.state == State.AIRBORNE:
            dur = ""
            if dev.airborne_since:
                m = (datetime.now(timezone.utc) - dev.airborne_since).total_seconds() / 60
                dur = f" · {int(m)}min"
            lines.append(
                f"{icon} *{dev.name}* "
                f"{b.alt_m:.0f}m AMSL · {b.speed_kmh:.0f}km/h{dur} · {age_label}"
            )
        else:
            lines.append(f"{icon} *{dev.name}* {b.alt_m:.0f}m AMSL · {age_label}")

    return "\n".join(lines)


def _format_detail(dev: DeviceState, lang: str = DEFAULT_LANGUAGE) -> str:
    msgs  = MESSAGES.get(lang, MESSAGES[DEFAULT_LANGUAGE])
    icon  = _state_icon(dev.state)
    lines = [f"{icon} *{dev.name}* — {dev.state.name.replace('_', ' ')}"]
    if dev.airborne_since:
        m = (datetime.now(timezone.utc) - dev.airborne_since).total_seconds() / 60
        lines.append(msgs["airborne_since"].format(min=int(m)))
    if dev.last_beacon:
        b   = dev.last_beacon
        age = int((datetime.now(timezone.utc) - b.ts).total_seconds())
        lines += [
            f"Alt: {b.alt_m:.0f}m AMSL · {b.agl_m:.0f}m AGL",
            f"Speed: {b.speed_kmh:.0f}km/h · Vspeed: {b.vspeed_ms:+.1f}m/s "
            f"· Course: {b.course_deg:.0f}°",
            f"Source: {b.source} · {_fmt_age(age, lang)}",
            b.maps_url,
        ]
    else:
        lines.append(msgs["no_data"])
    return "\n".join(lines)


def _pilot_keyboard(devices: dict) -> dict:
    rows, row = [], []
    for dev in sorted(_unique_devices(devices), key=lambda d: d.name):
        row.append({"text": f"{_state_icon(dev.state)} {dev.name}",
                    "callback_data": f"pilot:{dev.name}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "\U0001f504 Refresh", "callback_data": "refresh"}])
    return {"inline_keyboard": rows}


def _bot_send(chat_id, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload, timeout=10,
        ).raise_for_status()
    except Exception as e:
        print(f"  [BOT] send error: {e}")


def _bot_edit(chat_id, message_id: int, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "message_id": message_id,
               "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            json=payload, timeout=10,
        ).raise_for_status()
    except Exception as e:
        print(f"  [BOT] edit error: {e}")


def _handle_update(update: dict, all_devices: dict) -> None:
    if "message" in update:
        msg     = update["message"]
        text    = msg.get("text", "")
        chat_id = msg["chat"]["id"]

        if text.startswith("/setup"):
            _bot_send(chat_id, f"Chat ID: `{chat_id}`")
            return

        wl = _db.get_watchlist_by_chat_id(str(chat_id))
        if wl is None:
            return
        lang    = wl.get("language", DEFAULT_LANGUAGE)
        msgs    = MESSAGES.get(lang, MESSAGES[DEFAULT_LANGUAGE])
        wl_devs = _devices_for_watchlist(all_devices, wl["id"])

        if text.startswith("/status"):
            _bot_send(chat_id, _format_summary(wl_devs, lang=lang),
                      reply_markup=_pilot_keyboard(wl_devs))

        elif text.startswith("/lang"):
            parts = text.strip().split()
            if len(parts) == 2 and parts[1] in SUPPORTED_LANGUAGES:
                _db.update_watchlist_language(wl["id"], parts[1])
                reply = MESSAGES[parts[1]]["lang_set"]
            else:
                reply = msgs["lang_unknown"].format(langs=", ".join(sorted(SUPPORTED_LANGUAGES)))
            _bot_send(chat_id, reply)

    elif "callback_query" in update:
        cq      = update["callback_query"]
        data    = cq["data"]
        chat_id = cq["message"]["chat"]["id"]
        msg_id  = cq["message"]["message_id"]

        wl = _db.get_watchlist_by_chat_id(str(chat_id))
        if wl is None:
            return
        lang    = wl.get("language", DEFAULT_LANGUAGE)
        wl_devs = _devices_for_watchlist(all_devices, wl["id"])

        try:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": cq["id"]}, timeout=5,
            )
        except Exception:
            pass

        if data == "refresh":
            _bot_edit(chat_id, msg_id, _format_summary(wl_devs, lang=lang),
                      reply_markup=_pilot_keyboard(wl_devs))
        elif data.startswith("pilot:"):
            name = data[6:]
            dev  = next((d for d in _unique_devices(wl_devs) if d.name == name), None)
            if dev:
                _bot_send(chat_id, _format_detail(dev, lang=lang))


def bot_thread(all_devices: dict, stop_flag) -> None:
    offset = 0
    print("  [BOT] starting long-poll getUpdates")
    while not stop_flag.is_set():
        try:
            r = httpx.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 25,
                        "allowed_updates": ["message", "callback_query"]},
                timeout=30,
            )
            updates = r.json().get("result", [])
        except Exception as e:
            print(f"  [BOT] getUpdates error: {e}")
            stop_flag.wait(5)
            continue
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                _handle_update(upd, all_devices)
            except Exception as e:
                print(f"  [BOT] handle error: {e}")
