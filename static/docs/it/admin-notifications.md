## Admin — Notifiche

Configura quali eventi vengono inviati via Telegram per ogni watchlist.

### Prerequisito

La watchlist deve avere un **chat ID Telegram** configurato. Vai in Impostazioni watchlist, aggiungi il bot al canale e usa `/setup` per trovare l'ID.

### Tipi di evento

Le conferme sono espresse in **secondi**, non in numero di beacon: le sorgenti trasmettono a ritmi molto diversi (FANET ogni ~2s, GrappaSafe ogni 15s, PureTrack ogni ~30s), e contare i beacon faceva sì che la stessa soglia valesse quattro secondi su una sorgente e un minuto su un'altra. Tutti i valori qui sotto sono i default e si cambiano dalla pagina **Soglie**.

- **Decollo** — velocità ≥ 20 km/h per 20 secondi, oppure quota AGL > 150m (in quota il volo è certo: nessuna attesa). Sempre attivo.
- **Atterraggio** — AGL ≤ 50m e velocità ≤ 10 km/h per 45 secondi. Sempre attivo.
- **Aria brutta** — variometro ≤ −8 m/s con velocità bassa (≤ 20 km/h) e AGL > 150m, per 8 secondi. È l'evento informativo «sta scendendo forte»: la rete vera per la riserva è quella sotto. Sempre attivo.
- **Atterraggio duro** — discesa rapida (variometro ≤ −6 m/s) seguita da arresto improvviso a terra. Sempre attivo.
- **Possibile riserva** 🚨 — vedi sotto. Sempre attivo.
- **Possibile impatto** 🚨 — vedi sotto. Sempre attivo.
- **Climbing well** — variometro ≥ 3 m/s in modo continuato per almeno 2 minuti. Una volta per termica.
- **In orbita** — il pilota ha superato i 1500m AGL. Una volta per volo.
- **Piange giallo** — il pilota è in volo da più di 4 ore. Una volta per volo.
- **Ha fatto strada** — il pilota si è allontanato 30 km o più dal punto di decollo. Una volta per volo.
- **Segnale perso** — nessun beacon da oltre 10 minuti, **solo per un pilota in volo**. Se il segnale sparisce quando è già atterrato, quasi sempre ha solo spento lo strumento: la transizione avviene in silenzio, e così anche il ritorno.
- **Segnale ritrovato** — segnale recuperato dopo una perdita che era stata annunciata.

### Le due reti di sicurezza

**Possibile riserva.** Una vela di soccorso scende a 5-6 m/s: sotto la soglia dell'aria brutta, che quindi non la vede mai. Questa rete non guarda quanto è ripida la discesa ma **come finisce**. Si arma su una discesa a −5 m/s sostenuta per 12 secondi, e solo se il pilota è davvero decollato. Si disarma solo se rientra in volo per davvero — variometro risalito **e** ancora in velocità di volo — così una spirale o un B-stall voluti non allarmano. Se invece la discesa finisce, scatta in due modi: il pilota resta **fermo** entro 60 m per 2 minuti (vale anche appeso a un albero), oppure il **beacon tace vicino a terra**. Se sparisce in quota non si allarma: lassù il silenzio non è distinguibile da un buco di copertura.

**Possibile impatto.** Solo per i piloti che usano l'app GrappaSafe: l'app manda il picco dell'accelerometro, che nessun beacon radio ha. Una botta sopra i 10 g seguita da 2 minuti di immobilità fa scattare l'allarme. Chi si rialza e si allontana dal punto non allarma nessuno.

Entrambe sono **sempre attive** e non disattivabili per watchlist: una watchlist esiste per essere avvisata quando un volo va storto.

### Come configurare

Seleziona la watchlist e usa i toggle per abilitare o disabilitare ogni evento. Le modifiche sono salvate immediatamente. Le soglie numeriche stanno nella pagina **Soglie**.
