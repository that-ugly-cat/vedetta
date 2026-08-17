## Admin — Notifications

Configure which events are sent via Telegram for each watchlist.

### Prerequisite

The watchlist must have a **Telegram chat ID** configured. Go to Watchlist settings, add the bot to the channel and use `/setup` to find the ID.

### Event types

Confirmations are expressed in **seconds**, not in number of beacons: the sources transmit at very different rates (FANET every ~2s, GrappaSafe every 15s, PureTrack every ~30s), and counting beacons made the same threshold mean four seconds on one source and a minute on another. The values below are the defaults; they are edited on the **Thresholds** page.

- **Takeoff** — speed ≥ 20 km/h for 20 seconds, or AGL above 150m (at that height the flight is certain: no waiting). Always active.
- **Landing** — AGL ≤ 50m and speed ≤ 10 km/h for 45 seconds. Always active.
- **Rough air** — variometer ≤ −8 m/s with low speed (≤ 20 km/h) and AGL > 150m, for 8 seconds. This is the informational "sinking fast" event: the real reserve net is the one below. Always active.
- **Hard landing** — rapid descent (variometer ≤ −6 m/s) followed by a sudden stop on the ground. Always active.
- **Possible reserve** 🚨 — see below. Always active.
- **Possible impact** 🚨 — see below. Always active.
- **Climbing well** — variometer ≥ 3 m/s continuously for at least 2 minutes. Once per thermal.
- **Soaring high** — pilot has exceeded 1500m AGL. Once per flight.
- **Flying 4+ hours** — pilot has been flying for more than 4 hours. Once per flight.
- **Covered distance** — pilot has moved 30 km or more from the takeoff point. Once per flight.
- **Signal lost** — no beacon for more than 10 minutes, **only for a pilot in flight**. If the signal disappears once they have landed, they almost certainly just switched the instrument off: the transition happens silently, and so does the recovery.
- **Signal found** — signal recovered after a loss that had been announced.

### The two safety nets

**Possible reserve.** A reserve canopy comes down at 5-6 m/s: below the rough-air threshold, which is why that one never sees it. This net does not look at how steep the descent is but at **how it ends**. It arms on a descent at −5 m/s sustained for 12 seconds, and only if the pilot actually took off. It disarms only on a genuine recovery — variometer back up **and** still at flight speed — so an intentional spiral or B-stall raises nothing. If instead the descent ends, it fires in one of two ways: the pilot stays **still** within 60 m for 2 minutes (hanging in a tree counts), or the **beacon goes quiet near the ground**. A descent that vanishes high up does not alarm: up there, silence is indistinguishable from a coverage hole.

**Possible impact.** Only for pilots using the GrappaSafe app, which forwards the accelerometer peak — something no radio beacon carries. A hit above 10 g followed by 2 minutes of immobility raises the alarm. Someone who gets up and walks away from the spot alarms nobody.

Both are **always active** and cannot be switched off per watchlist: a watchlist exists to be told when a flight goes wrong.

### How to configure

Select the watchlist and use the toggles to enable or disable each event. Changes are saved immediately. The numeric thresholds live on the **Thresholds** page.
