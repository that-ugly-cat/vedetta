## Admin — Thresholds

Every number the state machine and the two safety nets work with. They used to be environment variables: changing one meant rebuilding the Docker image. Now they are edited here, and go **live within a minute** with no restart.

Each field saves itself when you leave the box: a green border confirms, a red one means the value was not accepted.

### Why seconds and not beacons

The sources transmit at very different rates: FANET every ~2 seconds, the GrappaSafe app every 15, PureTrack every ~30. As long as confirmations were counted in beacons, "two consecutive beacons" meant four seconds for a pilot on FANET and a minute for one followed through PureTrack — same rule, incomparable behaviour. Every confirmation is now a duration.

### The groups

**Flight — state machine.** Takeoff, landing, and the certainty altitude. `airborne_alt_m` is the AGL height above which the flight is not in doubt: there the state flips to airborne **at once**, with no confirmation, because with gappy reception every confirmation would be wiped by the silence and a pilot at altitude would stay pinned to "on the ground". `max_gap_s` is the silence beyond which confirmations in progress are dropped: two beacons twenty minutes apart are not a confirmation.

**Informational events.** Rough air and hard landing. These are notifications, not alarms: they say "sinking fast", not "something happened".

**Reserve net.** The descent that *ends* instead of *recovering*. `chute_arm_vspeed_ms` (−5) is the rate that arms the watch; lowering it in absolute value (towards −4) makes it more sensitive and noisier, raising it (towards −6) risks missing a slow reserve. `chute_confirm_s` is how long the descent must last to arm, and how long the recovery must last to disarm. `chute_immobile_s` is the immobility that confirms the alarm.

**Impact net.** Only for pilots using the GrappaSafe app, the one source that sends the accelerometer peak. `impact_g` at 0 disables the net. 10 g is a cautious starting point — a normal landing is around 1-3 g — but it is exactly the kind of number that needs tuning against real tracks.

**Sources and signal.** How much silence declares the signal lost, and how long a radio beacon takes precedence over the same pilot's internet-based sources.

**Tracks on the map.** A track is the **whole current flight**, not the last N beacons: it used to be a hundred points, which is three minutes of flight on FANET and nearly an hour on PureTrack — the same line meaning different things depending on the receiver. `track_gap_min` is the silence that separates one flight from the previous one: past that threshold the track is cut there. `track_keep_min` is how long a track stays visible after the last beacon, so a flight does not vanish the moment the pilot lands; on the map a finished flight is drawn dashed and paler than someone still flying. `track_max_points` is the cap above which the track is thinned: four hours of FANET are seven thousand points, which no line redrawn every few seconds can carry.

**Milestones.** The thresholds of the cheerful notifications: height for "soaring high", hours for "flying 4+ hours", kilometres for "covered distance", climb rate and duration for "climbing well".

### One warning

These thresholds decide whether an alarm goes out at all. Raising them cuts false positives and adds false negatives, and the second kind of error costs far more than the first. When in doubt, leave the default: those are the values tuned on GrappaSafe, which runs on the same kind of data.
