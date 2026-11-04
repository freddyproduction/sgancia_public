# Cronologia, contestazioni e gestione dei membri

## Spese e contestazioni

L’icona cronologia accanto alla spesa apre tutte le versioni autorizzate. Selezionando una versione si confrontano il contenuto precedente e successivo: titolo, note, data, categoria, voci, divisioni, quote, pagatori, valuta e cambio conservato. Autore e data sono mostrati per ogni versione. Le versioni economiche originali non vengono riscritte.

Una persona con una quota o un anticipo può aprire una contestazione motivata sulla versione corrente. Non è ammessa una seconda contestazione aperta della stessa persona sulla stessa spesa. Il richiedente può ritirarla; autore della spesa o gestore autorizzato, diverso dal richiedente, può risolverla o respingerla con motivazione. La contestazione non modifica il ledger: eventuali correzioni si salvano con Modifica spesa e producono una nuova versione. Nei gruppi archiviati e per i visualizzatori la cronologia è consultabile senza scritture.

Una rivelazione rende pubblica la versione corrente, senza pubblicare automaticamente vecchie versioni riservate, motivazioni riferite a esse o documenti caricati quando erano riservate. Ogni accesso viene verificato rispetto al gruppo, al pubblico corrente e a quello della versione storica. L’amministratore non aggira la visibilità.

## Rimborsi

Cronologia rimborsi → Eventi e motivazioni mostra creazione, conferma, contestazione, risoluzione, annullamento e ripristino, con account agente e data. Le conversioni della valuta del gruppo sono mostrate separatamente con importo precedente/successivo e cambio; l’importo principale è esplicitamente quello attuale. I nuovi eventi hanno un ordinamento ad alta precisione; eventi legacy dello stesso secondo, privi di tale precisione, mantengono l’orario originale.

Il ricevente può contestare un pagamento in attesa, indicando il motivo. Una contestazione può terminare con conferma del ricevente dopo l’arrivo del denaro oppure annullamento da una delle persone autorizzate; l’esito richiede una motivazione. Per un ricevente senza account può operare il gestore o un delegato all’attestazione, sempre nel pubblico autorizzato. Un rimborso confermato può essere ripristinato dal ricevente autorizzato: torna il debito, mentre la precedente conferma resta nello storico. Queste operazioni non trasferiscono denaro.

## Gestione avanzata del gruppo

Impostazioni gruppo → Gestione avanzata raccoglie i percorsi seguenti. Le modifiche strutturali richiedono un gruppo attivo. Nei gruppi congelati restano utilizzabili i rimborsi consentiti; gli archiviati restano in sola lettura.

### Proprietà

Solo il proprietario può proporre il trasferimento a un altro membro con account attivo e scrittura. È richiesta un’identità confermata di recente, anche per l’accettazione. Il destinatario deve accettare dal proprio account entro 24 ore. Una proposta nuova o una modifica dei metadati rende la precedente obsoleta. All’accettazione il nuovo account diventa proprietario, quello precedente amministratore; gli inviti pendenti sono revocati. Nessun nuovo accesso alle spese riservate viene concesso dalla proprietà.

### Uscita e rimozione

Il proprietario deve prima trasferire la proprietà. Il membro può uscire; un gestore può rimuovere un altro partecipante, ma solo il proprietario può rimuovere un altro amministratore. Prima viene generata un’anteprima verificata anche al salvataggio. Ogni ambito economico resta distinto; si considerano rimborsi pendenti/contestati e debiti diretti anche con saldo netto zero.

Con saldi aperti occorre scegliere esplicitamente di conservarli. Il partecipante diventa un virtuale inattivo con lo stesso ID: l’account perde l’accesso, mentre spese, file, anticipi, debiti, ricevute e autori storici restano conservati. La rimozione effettuata da un altro account richiede sempre conservazione integrale e non espone importi o presenza di ambiti nascosti. Inviti personali, claim e deleghe interessate vengono revocati. Il gestore può attestare i rimborsi per il virtuale uscente. Per ricollegare un account: riattivare la persona e poi emettere un nuovo invito/claim; la riattivazione da sola non restituisce accesso ad alcun account.

### Fusione

Una sorgente virtuale attiva può essere unita a un’altra persona attiva, con o senza account. Non si uniscono due account registrati differenti sulla base del nome. L’anteprima mostra persone, spese/rimborsi interessati e saldi prima/dopo negli ambiti autorizzati. Il salvataggio verifica l’impronta dei dati e prende un lock del gruppo.

La fusione richiede accessi riservati equivalenti per entrambe le persone, anche nelle vecchie versioni, e autorizzazione del gestore su tutti gli ambiti interessati. Rimborsi tra le due identità bloccano l’operazione: richiedono prima una riconciliazione dedicata. Questi rifiuti sono conservativi, senza modificare dati o allargare visibilità.

Quote e anticipi sono sommati in nuove revisioni, con importi esatti nella valuta del gruppo; i totali non cambiano e le vecchie revisioni restano intatte. Le identità correnti dei rimborsi sono aggiornate con eventi espliciti e snapshot dell’operazione. La sorgente resta conservata come identità storica unita. Inviti, claim e deleghe interessate sono revocati.

“Ripristina fusione” è disponibile solo se non sono intervenute ulteriori modifiche rilevanti nel gruppo: crea nuove revisioni di rettifica, ripristina le identità e conserva anche la fusione nello storico. Dopo ulteriori modifiche il ripristino automatico è bloccato per evitare di annullare lavoro successivo. I vecchi inviti e deleghe non vengono riattivati.

### Deleghe e associazione

Il gestore assegna una delega a un account con scrittura per un virtuale attivo, scegliendo separatamente pagamento e attestazione, con validità da 1 a 90 giorni. Le deleghe non aggiungono la persona a pubblici riservati. Il delegato vede le proprie deleghe; i gestori possono consultarle e revocarle. Scadenza, revoca, uscita, fusione o associazione a un account interrompono i permessi.

Nei rimborsi il delegato al pagamento può selezionare il virtuale come mittente. Il delegato all’attestazione può confermare/contestare/ripristinare per un ricevente virtuale autorizzato; Saldato compare anche nei suggerimenti del gruppo. Il nome dell’account che opera resta negli eventi.

Per un virtuale esistente, “Associa un account” genera un codice di 24 ore vincolato all’email del destinatario. Nella panoramica il destinatario usa “Associa partecipante”. Il codice è monouso; un nuovo codice revoca quelli precedenti. Se l’account ha già un partecipante nel gruppo è necessaria una fusione controllata. Per nuovi account rimane il percorso Inviti e ospiti, con le politiche dell’installazione.
