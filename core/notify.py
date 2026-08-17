import httpx

import db as _db
from core.config import TELEGRAM_TOKEN
from core.state_machine import Event
from messages import DEFAULT_LANGUAGE, MESSAGES

# The two safety nets are not opt-out, like takeoff/landing and the two
# informational alarms: a watchlist exists to be told when a flight goes wrong.
ALWAYS_ON_EVENTS = {"takeoff", "landing", "bad_air", "bad_landing", "reserve", "impact"}


def _format_event(event: Event, lang: str = DEFAULT_LANGUAGE) -> str:
    b    = event.beacon
    msgs = MESSAGES.get(lang, MESSAGES[DEFAULT_LANGUAGE])
    tpl  = msgs.get(event.kind.value, "{name}\n{loc}")
    return tpl.format(
        name  = b.name,
        alt   = f"{b.alt_m:.0f}",
        speed = f"{b.speed_kmh:.0f}",
        loc   = b.maps_url,
        note  = event.note,
    )


def _send_telegram(chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  [Telegram→{chat_id}] {e}")


def notify(events: list, dry_run: bool = False) -> None:
    for ev in events:
        event_key  = ev.kind.value
        watchlists = _db.get_watchlists_for_device_name(ev.beacon.name)
        for wl in watchlists:
            wl_id   = wl["id"]
            chat_id = wl.get("telegram_chat_id")
            lang    = wl.get("language", DEFAULT_LANGUAGE)
            if not chat_id:
                continue
            if event_key not in ALWAYS_ON_EVENTS:
                if not _db.is_event_enabled_wl(wl_id, event_key):
                    continue
            msg = _format_event(ev, lang=lang)
            if dry_run:
                print(f"  [notify→{chat_id}] {msg}")
            else:
                _send_telegram(chat_id, msg)
