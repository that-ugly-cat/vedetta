## My devices

A **device** is a GPS tracking instrument associated with your account. Each device can have multiple **sources** — identifiers on different networks — that vedetta uses in parallel to receive your position.

### Adding or editing a device

Enter a **display name** (e.g. "Giovanni") and at least one source with its ID. The display name is what appears on the map and in Telegram notifications.

### Available sources

- **FANET** — Skytraxx/FLARM network for paragliding and hang gliding. Update every ~2s. Requires a nearby OGN ground station to receive the radio signal.
- **FLARM** — anti-collision for gliders and light aircraft. Same OGN radio coverage as FANET. Many modern variometers transmit on both.
- **OGN Tracker** — dedicated OGN tracker (e.g. T-Beam) or Android **OGN Tracker** app. Good alpine coverage, long battery life.
- **Naviter** — Oudie/Syride devices with internet connectivity. Data arrives via cloud, not radio: **does not depend on OGN coverage**, but the device must have active mobile data.
- **ICAO** — code for certified aircraft.
- **PureTrack** — tracking platform that aggregates many different sources. In vedetta you enter only the pilot's **PureTrack username** (e.g. `mario-rossi`), not URLs or other identifiers.
- **GrappaSafe** — the monitoring app of the Consorzio Vivere il Grappa. Here you don't enter an ID but a **token**: press *Generate*, save the device, then paste the token into the GrappaSafe app (Settings → Data forwarding). It is the only source that *pushes* data to vedetta instead of being read off a network.

### GrappaSafe: the app that sends data to vedetta

If you fly with the GrappaSafe app, your positions can reach vedetta too, with nothing else to install:

1. In vedetta: open your device, press **Generate** on the GrappaSafe row, and **save**
2. Copy the token
3. In the GrappaSafe app: **Settings → Data forwarding → Vedetta**, paste the token, switch it on

From then on every position the app sends to the GrappaSafe server is forwarded to vedetta as well, which treats it like any other beacon: map pin, track, flight state and **Telegram notifications to the watchlist** (takeoff, landing, thermals, and the rest).

Two things to know. First, **OGN takes precedence**. If the same device has been receiving radio beacons (FANET/FLARM) in the last 90 seconds, GrappaSafe points are ignored — the radio signal is more accurate, especially on vertical speed. The GrappaSafe channel steps in when the radio goes quiet. Second, **the token is a key**. Whoever holds it can write positions in your name. If you think it has leaked, generate a new one and save: the old one stops working within two minutes.

Only the **position** is forwarded. Emergency contacts and medical data stay inside GrappaSafe: vedetta neither receives nor asks for them.

### OGN Tracker app: an alternative without dedicated hardware

If you don't have a radio transponder, you can use the **OGN Tracker** app (Android) to be visible on the OGN network. The app uses your phone's GPS and mobile data to send your position directly to the OGN servers.

Setup:

1. Install **OGN Tracker** from the Play Store
2. Open the app: you'll find your **OGN ID** on the main screen (a hexadecimal code, e.g. `E3BDED`)
3. Register the device at [ddb.glidernet.org](https://ddb.glidernet.org) with that code — this links your ID to your data and makes you recognisable to other pilots
4. Add the ID in vedetta as an **OGN Tracker** source

Advantage: your position is visible to all systems that aggregate OGN data — in-cockpit displays with SkyDemon, XCTrack, and the OGN community in general. However, it depends on mobile coverage, like PureTrack.

There is no equivalent app for iOS with direct access to the OGN network. iOS pilots can use PureTrack as an alternative.

### PureTrack: a source aggregator

PureTrack is not just an app: it is a platform that collects data from many different sources. Once a pilot has a PureTrack account and has connected their instruments, vedetta receives everything automatically via their username. Sources supported by PureTrack include:

- **FLARM** — radio transponder; if the pilot has FLARM, PureTrack receives it and vedetta sees it even without configuring the FLARM source separately
- **XContest / XCTrack** — XContest live tracking appears on PureTrack automatically
- **Oudie / SeeYou Navigator** — Naviter variometers with connectivity
- **Syride** — Syride variometers with connectivity
- **IGC Droid** — Android app for those without dedicated hardware
- **Garmin inReach** — two-way satellite, works without mobile coverage
- **ADSB** — aircraft with ADS-B transponders
- **SSA / SoaringSpot / FFVL** — integrations for competitions

For full details and setup instructions for each source, see [puretrack.io/help](https://puretrack.io/help).

### FANET/FLARM vs app: what's the difference?

The ideal is for every pilot to have a **radio transponder** (FANET or FLARM):

- Direct radio transmission, **no dependency on mobile network**
- Very low latency (~2s), continuous updates even in remote altitude
- **Air-to-air visibility**: other pilots with FANET see your position on their display
- **Visibility to aircraft**: FLARM transponders are received by many general aviation aircraft and anti-collision systems

App-based sources (PureTrack, Naviter) use the mobile network: they work well at takeoff and landing, but may drop out at altitude or in areas without signal. They remain useful for finding a pilot who has **landed out** — on the ground far away in a valley where the OGN radio signal doesn't reach but mobile coverage exists.

### Source priority (one device, multiple sources)

If a device has multiple active sources, vedetta does not apply a fixed priority: it always uses the **most recent beacon**, regardless of where it comes from. If FANET updates every 2s and PureTrack every 30s, the map will show FANET data.

### Multiple devices

If you have multiple instruments (e.g. main vario + GPS backup), you can register multiple devices. Use **different display names** to see them as separate pins on the map.

If two devices have the same display name, their beacons are merged: vedetta always shows the most recent position between the two, as if they were a single pilot.

### Pin colour

The chosen colour is used both for the pin on the map and for the flight track. You can change it at any time by editing the device.
