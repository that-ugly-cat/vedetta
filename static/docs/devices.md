## I miei device

Un **device** è uno strumento di tracciamento GPS associato al tuo account. Ogni device può avere più **sorgenti** — identificatori su reti diverse — che vedetta usa in parallelo per ricevere la tua posizione.

### Aggiungere o modificare un device

Inserisci un **nome display** (es. "Giovanni") e almeno una sorgente con il relativo ID. Il nome display è quello che appare sulla mappa e nelle notifiche Telegram.

### Sorgenti disponibili

- **FANET** — rete Skytraxx/FLARM per parapendio e deltaplano. Aggiornamento ogni ~2s. Richiede una stazione OGN nelle vicinanze che riceva il segnale radio.
- **FLARM** — anticollisione per alianti e aviazione leggera. Stessa copertura radio OGN di FANET. Molti variometri recenti trasmettono su entrambi.
- **OGN Tracker** — tracker OGN dedicato (es. T-Beam) o app Android **OGN Tracker**. Buona copertura alpina, batteria lunga.
- **Naviter** — dispositivi Oudie/Syride con connettività internet. I dati arrivano via cloud, non via radio: **non dipende dalla copertura OGN**, ma il device deve avere dati mobili attivi.
- **ICAO** — codice per aeromobili certificati.
- **PureTrack** — piattaforma di tracciamento che aggrega molte fonti diverse. In vedetta inserisci solo lo **username PureTrack** del pilota (es. `mario-rossi`), non URL o altri identificatori.

### PureTrack: un aggregatore di fonti

PureTrack non è solo un'app: è una piattaforma che raccoglie dati da molte sorgenti diverse. Una volta che il pilota ha un account PureTrack e ha collegato i suoi strumenti, vedetta riceve tutto automaticamente tramite il suo username. Le sorgenti supportate da PureTrack includono:

- **FLARM** — transponder radio; se il pilota ha FLARM, PureTrack lo riceve e vedetta lo vede anche senza configurare la sorgente FLARM separatamente
- **XContest / XCTrack** — live tracking XContest appare su PureTrack automaticamente
- **Oudie / SeeYou Navigator** — variometri Naviter con connettività
- **Syride** — variometri Syride con connettività
- **IGC Droid** — app Android per chi non ha hardware dedicato
- **Garmin inReach** — satellite bidirezionale, funziona senza copertura cellulare
- **ADSB** — aeromobili con transponder ADS-B
- **SSA / SoaringSpot / FFVL** — integrazioni per competizioni

Per il dettaglio completo e le istruzioni di configurazione di ogni sorgente, vedi [puretrack.io/help](https://puretrack.io/help).

Questo significa che anche piloti senza hardware dedicato possono essere monitorati da vedetta, a patto che abbiano un account PureTrack e connettività dati attiva sul dispositivo.

### OGN Tracker app: un'alternativa senza hardware dedicato

Se non hai un transponder radio, puoi usare l'app **OGN Tracker** (Android) per essere visibile sulla rete OGN. La app usa il GPS del telefono e la rete cellulare per inviare la tua posizione direttamente ai server OGN.

Configurazione:

1. Installa **OGN Tracker** dal Play Store
2. Apri l'app: trovi il tuo **OGN ID** nella schermata principale (un codice esadecimale, es. `E3BDED`)
3. Registra il device su [ddb.glidernet.org](https://ddb.glidernet.org) con quel codice — questo associa il tuo ID ai tuoi dati e lo rende riconoscibile agli altri piloti
4. Aggiungi l'ID in vedetta come sorgente **OGN Tracker**

Vantaggi: la tua posizione è visibile a tutti i sistemi che aggregano dati OGN — display di bordo con SkyDemon, XCTrack, e in generale la community OGN. Dipende però dalla copertura cellulare, come PureTrack.

Per iOS non esiste un'app equivalente con accesso diretto alla rete OGN. I piloti iOS possono usare PureTrack come alternativa.

### FANET/FLARM vs app: qual è la differenza?

L'ideale è che ogni pilota abbia un **transponder radio** (FANET o FLARM):

- Trasmissione radio diretta, **nessuna dipendenza dalla rete cellulare**
- Latenza bassissima (~2s), aggiornamenti continui anche in quota remota
- **Visibilità air-to-air**: altri piloti con FANET vedono la tua posizione sul loro display
- **Visibilità agli aerei**: i transponder FLARM sono ricevuti da molti aerei dell'aviazione generale e dai sistemi anticollisione

Le sorgenti basate su app (PureTrack, Naviter) usano la rete cellulare: funzionano bene al decollo e all'atterraggio, ma possono interrompersi in quota o in zone senza segnale. Rimangono però utili per trovare un pilota che ha **bucato** — atterrato lontano in valle dove il segnale radio OGN non arriva ma c'è copertura cellulare.

### Priorità tra sorgenti (un device, più sorgenti)

Se un device ha più sorgenti attive, vedetta non applica una priorità fissa: usa sempre il **beacon più recente**, indipendentemente da dove arriva. Se FANET aggiorna ogni 2s e PureTrack ogni 30s, la mappa mostrerà i dati FANET.

### Device multipli

Se hai più strumenti (es. vario principale + backup GPS), puoi registrare più device. Usa **nomi display diversi** per vederli come pin separati sulla mappa.

Se due device hanno lo stesso nome display, i loro beacon vengono unificati: vedetta mostra sempre la posizione più recente tra i due, come se fossero un unico pilota.

### Colore pin

Il colore scelto viene usato sia per il pin sulla mappa sia per la traccia di volo. Puoi modificarlo in qualsiasi momento aggiornando il device.
