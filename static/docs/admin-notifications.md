## Admin — Notifiche

Configura quali eventi vengono inviati via Telegram per ogni watchlist.

### Prerequisito

La watchlist deve avere un **chat ID Telegram** configurato. Vai in Impostazioni watchlist, aggiungi il bot al canale e usa `/setup` per trovare l'ID.

### Tipi di evento

- **Decollo** — velocità ≥ 20 km/h o quota AGL > 150m per 2 beacon consecutivi. Sempre attivo.
- **Atterraggio** — AGL ≤ 50m e velocità ≤ 10 km/h per 3 beacon consecutivi. Sempre attivo.
- **Aria brutta** — variometro ≤ −8 m/s con velocità bassa (≤ 20 km/h) e AGL > 150m. Possibile vela collassata. Sempre attivo.
- **Atterraggio duro** — discesa rapida (variometro ≤ −6 m/s) seguita da arresto improvviso a terra. Sempre attivo.
- **Climbing well** — variometro ≥ 3 m/s in modo continuato per almeno 2 minuti. Una volta per volo.
- **In orbita** — il pilota ha superato i 1500m AGL. Una volta per volo.
- **Piange giallo** — il pilota è in volo da più di 4 ore. Una volta per volo.
- **Ha fatto strada** — il pilota si è allontanato 30 km o più dal punto di decollo. Una volta per volo.
- **Segnale perso** — nessun beacon ricevuto da oltre 10 minuti.
- **Segnale ritrovato** — segnale recuperato dopo una perdita.

### Come configurare

Seleziona la watchlist e usa i toggle per abilitare o disabilitare ogni evento. Le modifiche sono salvate immediatamente.
