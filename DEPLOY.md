# Deploy di vedetta

Una singola app FastAPI con un file SQLite. I worker (OGN, PureTrack, bot Telegram,
timeout) girano in thread dentro lo stesso processo: non c'è nient'altro da avviare.

## 1. Configurazione

Copia `.env.example` in `.env` e riempilo:

| Variabile | Obbligatoria | Default | Scopo |
|---|---|---|---|
| `SECRET_KEY` | **sì, in produzione** | `change-me-in-production` | firma il cookie di sessione — mettici un valore lungo e casuale |
| `WEBAPP_DB` | no | `webapp.db` | percorso del file SQLite (`/app/data/webapp.db` in Docker) |
| `TELEGRAM_TOKEN` | sì, per le notifiche | — | token del bot BotFather |
| `APRS_USER` | no | `OE1FW` | callsign di ricezione OGN/APRS; il passcode ne deriva, tienilo corto e unico |
| `TILE_DIR` | no | `/app/srtm_tiles` | tile SRTM per la quota AGL |

Le **soglie** di rilevamento non stanno qui: vivono nella tabella `config` e si modificano
dalla pagina admin **Soglie**. Le vecchie variabili d'ambiente (`TAKEOFF_SPEED_KMH`,
`SIGNAL_LOST_MIN`, …) restano lette **solo** per seminare la tabella al primo avvio su un
database che non ce l'ha ancora, così un deployment che le aveva personalizzate non le
perde. Dopo, il database è l'unica fonte di verità.

Genera un secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Tile SRTM

La quota AGL serve alla macchina a stati e a entrambe le reti di sicurezza: senza tile,
`compute_agl` restituisce valori inutilizzabili e le soglie di quota non significano nulla.
Metti i `.hgt` che coprono la tua zona in `srtm_tiles/` (sorgente pubblica, niente auth).

## 3. Avvio

```bash
docker compose up -d --build
python seed.py <username> <password>     # primo admin, una volta sola
```

Il compose espone `127.0.0.1:8006` e monta due volumi: `./data` (database) e
`./srtm_tiles`. Davanti ci va un reverse proxy che termina HTTPS; in produzione è Caddy.

## 4. Aggiornamento

I file sono baked nell'immagine, quindi **ogni** modifica — anche a un file statico o a una
guida Markdown — richiede un rebuild:

```bash
cd /opt/apps/vedetta
git pull
docker compose up -d --build
```

**Prima di aggiornare, fai il backup**: è il tuo rollback.

```bash
tar czf ../vedetta-code-$(date +%F).tar.gz --exclude=data --exclude=srtm_tiles --exclude=.venv .
docker cp vedetta:/app/data/webapp.db ../vedetta-webapp-$(date +%F).db
```

Lo schema è idempotente (`CREATE TABLE IF NOT EXISTS` + seed `INSERT OR IGNORE`): un
riavvio su un database esistente aggiunge le tabelle nuove e allinea i metadati della
config senza toccare i valori impostati dall'admin. Non ci sono migrazioni da lanciare a
mano.

## 5. Verifica dopo il deploy

```bash
docker ps --filter name=vedetta
docker logs vedetta --since 5m
```

Nei log devi vedere il warm-start dei device, il thread OGN connesso con il suo filtro, e
il conteggio delle chiavi di config. La prima aggiunta di un device fa riconnettere il
thread OGN: segue un burst di pacchetti APRS e un picco di CPU per qualche secondo — è il
comportamento normale, non un problema.
