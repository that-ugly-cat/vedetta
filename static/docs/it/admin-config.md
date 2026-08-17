## Admin — Soglie

Tutti i numeri con cui lavorano la macchina a stati e le due reti di sicurezza. Prima stavano nelle variabili d'ambiente: cambiarne uno voleva dire ricostruire l'immagine Docker. Adesso si modificano da qui, e sono **attivi entro un minuto** senza riavviare nulla.

Ogni campo si salva da solo quando esci dalla casella: il bordo verde conferma, il rosso dice che il valore non è stato accettato.

### Perché in secondi e non in beacon

Le sorgenti trasmettono a ritmi molto diversi: FANET ogni ~2 secondi, l'app GrappaSafe ogni 15, PureTrack ogni ~30. Finché le conferme si contavano in beacon, «due beacon consecutivi» valeva quattro secondi per un pilota con il FANET e un minuto per uno seguito via PureTrack — stessa regola, comportamenti incomparabili. Ora ogni conferma è una durata.

### I gruppi

**Volo — macchina a stati.** Decollo, atterraggio e quota di certezza. `airborne_alt_m` è la quota AGL oltre cui il volo non è in dubbio: lì si passa in volo **subito**, senza attendere la conferma, perché con ricezione a buchi ogni conferma verrebbe azzerata dal silenzio e un pilota in quota resterebbe inchiodato a «a terra». `max_gap_s` è il silenzio oltre cui le conferme in corso si buttano: due beacon a venti minuti di distanza non sono una conferma.

**Eventi informativi.** Aria brutta e atterraggio duro. Sono notifiche, non allarmi: dicono «sta scendendo forte», non «è successo qualcosa».

**Rete riserva.** La discesa che *finisce* invece di *rientrare*. `chute_arm_vspeed_ms` (−5) è il rateo che arma la vigilanza; abbassarlo in valore assoluto (verso −4) la rende più sensibile e più rumorosa, alzarlo (verso −6) rischia di mancare una riserva lenta. `chute_confirm_s` è quanto deve durare la discesa per armare, e quanto deve durare il rientro per disarmare. `chute_immobile_s` è l'immobilità che conferma l'allarme.

**Rete impatto.** Vale solo per chi usa l'app GrappaSafe, l'unica sorgente che manda il picco dell'accelerometro. `impact_g` a 0 disattiva la rete. 10 g è un punto di partenza prudente — un atterraggio normale sta sull'1-3 g — ma è proprio il genere di numero che va tarato su tracce vere.

**Sorgenti e segnale.** Quanto silenzio serve per dichiarare il segnale perso, e per quanto tempo un beacon radio ha la precedenza sulle sorgenti via internet dello stesso pilota.

**Tracce sulla mappa.** La traccia è il **volo corrente per intero**, non gli ultimi N beacon: prima erano cento punti, cioè tre minuti di volo su FANET e quasi un'ora su PureTrack — la stessa linea che significava cose diverse a seconda del ricevitore. `track_gap_min` è il silenzio che separa un volo dal precedente: sopra quella soglia la traccia si taglia lì. `track_keep_min` è per quanto una traccia resta visibile dopo l'ultimo beacon, così un volo non svanisce nell'istante in cui il pilota atterra; sulla mappa il volo finito si vede tratteggiato e più pallido di chi sta ancora volando. `track_max_points` è il tetto oltre cui la traccia viene diradata: quattro ore di FANET sono settemila punti, che nessuna linea ridisegnata ogni pochi secondi può reggere.

**Milestone.** Le soglie delle notifiche simpatiche: quota per «in orbita», ore per «piange giallo», chilometri per «ha fatto strada», salita e durata per «in buon lift».

### Un avvertimento

Queste soglie decidono se un allarme parte o no. Alzarle riduce i falsi positivi e aumenta i falsi negativi, e il secondo tipo di errore costa molto più del primo. Se non sei sicuro, lascia il default: sono i valori tarati su GrappaSafe, che gira sullo stesso tipo di dati.
