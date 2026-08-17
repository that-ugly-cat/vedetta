<p align="center">
  <b>vedetta</b><br>
  <i>Live tracking e notifiche per chi vola libero.</i>
</p>

---

vedetta segue un gruppo di piloti di parapendio su una mappa, capisce cosa stanno facendo
e lo racconta su Telegram a chi li aspetta a terra: decollo, atterraggio, una bella
termica, la distanza percorsa — e, quando serve, che qualcosa è andato storto.

Non è un sistema di soccorso: è il tool con cui un gruppo di amici si tiene d'occhio a
vicenda. Per l'infrastruttura di sicurezza di un consorzio c'è
[GrappaSafe](https://github.com/that-ugly-cat/grappasafe), che condivide con vedetta buona
parte della macchina a stati e delle reti di rilevamento.

## Sorgenti

Un pilota è un **device** con uno o più identificatori su reti diverse; vedetta usa sempre
il beacon più recente, con la radio che ha la precedenza finché è fresca.

| Sorgente | Come arriva |
|---|---|
| FANET, FLARM, OGN Tracker, Naviter, ICAO | OGN/APRS, connessione TCP persistente |
| PureTrack | polling HTTP (aggrega FLARM, XCTrack, Naviter, inReach, ADSB…) |
| GrappaSafe | push HTTP su `/api/ingest`, con token — l'unica che porta anche il picco accelerometro |

## Cosa riconosce

Una macchina a stati kinematica (`GROUNDED / WALKING / AIRBORNE / SIGNAL_LOST`) le cui
transizioni sono confermate **nel tempo**, non contando i beacon: le sorgenti trasmettono a
ritmi molto diversi (FANET ogni ~2 s, PureTrack ogni ~30 s) e contarli faceva sì che la
stessa soglia valesse quattro secondi per un pilota e un minuto per un altro.

Sopra la macchina, due reti di sicurezza:

- **Riserva.** Una vela di soccorso scende a 5-6 m/s, un rateo che una soglia di "discesa
  rapida" non distingue da una spirale. Quello che le distingue non è la ripidezza ma
  **come finiscono**: la vigilanza si arma su una discesa sostenuta e si disarma solo se il
  pilota rientra davvero in volo (variometro risalito *e* ancora in velocità di volo, così
  un atterrato immobile non viene scambiato per un rientro). Se invece la discesa termina —
  il pilota resta fermo, anche appeso a un albero, o il beacon tace vicino a terra — parte
  l'allarme. Una discesa che sparisce in quota non allarma: lassù il silenzio è
  indistinguibile da un buco di copertura.
- **Impatto.** Solo per le sorgenti che portano un accelerometro: un picco oltre soglia
  seguito da immobilità prolungata. Chi si rialza e si allontana non allarma nessuno.

Tutte le soglie stanno nel database e si modificano dalla pagina admin **Soglie**, attive
entro un minuto senza riavviare.

## Stack

FastAPI + SQLite, Leaflet e JS vanilla sul frontend, `python-telegram-bot` per le
notifiche, quota AGL da tile SRTM locali. Tutto in un container.

```bash
pip install -r requirements.txt
python seed.py <username> <password>     # primo admin
uvicorn app:app --reload
```

Per il deploy in produzione vedi [DEPLOY.md](DEPLOY.md).

## Struttura

```
app.py               — rotte: auth, dashboard, API pilota/admin, ingest push
db.py                — schema SQLite, config a runtime, query
core/
  beacon.py          — dataclass Beacon e parser (OGN / PureTrack / push)
  state_machine.py   — stati, eventi, milestone
  emergency.py       — soglie (EmConfig) + reti riserva e impatto
  monitor.py         — thread OGN/PT/bot/timeout, hot-reload dei device
  ogn.py             — client APRS
  puretrack.py       — polling
  notify.py          — Telegram per watchlist
  terrain.py         — AGL da tile SRTM
  bot.py             — comandi del bot
templates/ static/   — Jinja2, Leaflet, guide contestuali in Markdown (IT/EN)
```
