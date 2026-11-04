# Modelli, ricorrenze e anticipi

Nel gruppo apri **Modelli, ricorrenze e anticipi**. Accanto a una spesa puoi duplicarla oppure usarla per creare un modello. Una duplicazione apre una bozza da controllare: non copia allegati, contestazioni, rimborsi o cronologia; rimuove i riferimenti ai partecipanti non più attivi e richiede un cambio aggiornato per le valute estere. Se mancano pagatori o quote esatte occorre correggerli prima del salvataggio: gli importi non sono riallocati silenziosamente.

## Modelli

Crea una bozza, controlla l’anteprima, quindi assegna un nome al modello. Con **Usa come nuova spesa** ottieni una nuova bozza con la data corrente, da controllare e salvare. Il modello in sé non modifica i saldi. Conserva titolo, note, tag, valuta, divisioni, pagatori e pubblico. I modelli riservati sono visibili soltanto alle persone selezionate; gli amministratori non aggirano questa regola. Ogni gruppo può contenere al massimo 200 modelli/ricorrenze.

## Ricorrenze

Scegli prima data, frequenza (giorni, settimane, mesi o anni), intervallo ed eventuale ultima data. Conferma esplicitamente l’autorizzazione alla creazione automatica. Non è una richiesta di pagamento: Sgancia registra la spesa nel libro contabile.

Le date usano **Europe/Rome**. Il worker controlla ogni 30 secondi: una spesa diventa elaborabile dalla mezzanotte locale della sua data, senza garantire un orario esatto. Nei mesi corti il giorno viene limitato all’ultimo disponibile, conservando l’ancora iniziale: 31 gennaio → 28/29 febbraio → 31 marzo. Il 29 febbraio nelle ricorrenze annuali torna il 29 negli anni bisestili.

Il calendario mostra fino a 12 prossime date e gli ultimi 100 lavori visibili. L’elaborazione recupera al massimo 10 date per ricorrenza a ogni passaggio. Un lavoro persistente ha chiave unica modello/data; la creazione della spesa e il completamento del lavoro sono nella stessa transazione. Due worker, un riavvio o un retry non devono generare la stessa spesa due volte.

Il cambio automatico usa il tasso di riferimento corrente all’esecuzione, anche per date recuperate dopo un arresto. Il cambio manuale rimane quello autorizzato nel modello. Un cambio non disponibile provoca tentativi ritardati fino a otto fallimenti; poi serve un controllo manuale.

Prima di ogni esecuzione sono verificati account attivo, appartenenza e ruolo dell’autore, stato del gruppo, valuta principale, pubblico e partecipanti attivi. In caso di variazioni incompatibili la ricorrenza si sospende; modificare il modello e riattivarlo esplicitamente. Non viene assegnata a un nuovo autore se l’account lascia e rientra nel gruppo.

L’autore può modificare e riattivare il proprio modello. Gli amministratori del gruppo possono sospendere o eliminare soltanto i modelli che possono vedere. Modificare una ricorrenza la lascia sospesa; le spese già generate rimangono immutabili salvo le normali revisioni. Alla riattivazione scegli se saltare le date passate (predefinito) o recuperarle. Eliminare un modello ferma il futuro senza eliminare le spese già create.

## Anticipi per spese future

In **Anticipi e rimborsi** scegli **Anticipo per spese future**, chi ha versato, chi ha ricevuto, importo, nota ed eventuale pubblico riservato. È consentito solo in un gruppo attivo. Il saldo cambia soltanto dopo la conferma del ricevente o del suo rappresentante autorizzato. La conferma attribuisce un credito a chi ha versato e un debito a chi ha ricevuto; il totale delle spese resta invariato. Le spese successive anticipate dal ricevente e gli eventuali rimborsi compensano questi saldi secondo gli ambiti di visibilità. Il registro non attribuisce ogni singolo euro a una specifica spesa futura.

Si usano le medesime ricevute, contestazioni, annullamenti e ripristini dei rimborsi. Non duplicare il versamento anche come spesa: la spesa andrà inserita quando viene effettivamente sostenuta.

## Tag e calcolatrice

Inserisci fino a 20 tag per spesa, separati da virgole, ciascuno di massimo 40 caratteri. Sono visibili con la spesa e nella sua cronologia; i tag di spese riservate non alimentano elenchi visibili a chi ne è escluso.

**Conserva le formule nella cronologia della spesa** è disattivato per le nuove spese. In tal caso vengono salvati soltanto i risultati degli importi monetari; se attivo restano anche le espressioni originali di importi, pagatori e quote esatte. Le vecchie versioni non vengono riscritte. Conversioni della valuta principale e fusioni producono nuove revisioni numeriche; le formule precedenti rimangono consultabili nella versione originaria.

## Esecuzione e ripristino

Il servizio Compose **worker** usa la stessa immagine e lo stesso PostgreSQL dell’applicazione, senza nuove porte. Non esegue cron sull’host. Con `docker compose up -d` si avvia anche questo servizio. Non esiste alcuna spesa automatica finché non si crea e autorizza una ricorrenza.

Backup e ripristino includono modelli, lavori, anticipi, tag e formule. Prima del ripristino fermare **api, mail e worker**. Il ripristino sospende tutte le ricorrenze: verificarle e riattivarle dal sito dopo il controllo. Una copia vecchia del database non contiene gli eventi avvenuti dopo quel backup; controllare le spese già sostenute prima di recuperare le date arretrate.
