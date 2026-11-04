# Importazione ed esportazione

Nel gruppo apri **Importa / esporta**. Dalla ricerca puoi esportare direttamente i risultati filtrati: conteggio e file riguardano tutte le pagine dei risultati, non soltanto la pagina mostrata.

## Esportare

- **CSV Sgancia:** una riga per spesa, con colonne leggibili e campi JSON per voci, pagatori, quote, pubblico, tag e riferimenti dei partecipanti. È reimportabile in Sgancia senza perdere le divisioni complesse supportate.
- **JSON Sgancia:** formato `sgancia.exchange/1`, con le stesse spese, riferimenti senza email/identità degli account e, senza filtri, saldi e pagamenti consultivi. Non sono credenziali né un ripristino dell’installazione.
- **PDF:** riepilogo impaginato di spese, dettagli e, senza filtri, trasferimenti ancora da effettuare. Usa solo font locali; i testi non vengono interpretati come HTML o risorse da caricare. I caratteri non coperti dal font vengono indicati come `[U+XXXX]`, senza essere sostituiti da glifi illeggibili. CSV e JSON mantengono il testo Unicode originale.

Sono esportate soltanto le spese correnti non nel cestino che il tuo account può vedere. Categorie, tag, importi, nomi e saldi di ambiti esclusi non compaiono. Un visualizzatore può esportare quello che può leggere, senza acquisire diritti di importazione. I riferimenti degli account vengono rappresentati come partecipanti del gruppo: non vengono esportati email, password, MFA, passkey, gate, inviti o metodi di pagamento.

Limite: 500 spese per esportazione; usare date e filtri per suddividere file più grandi. File finali fino a 20 MB, contenuto del report PDF entro 2 MB. Con filtri attivi non vengono inclusi i saldi/pagamenti dell’intero gruppo, per evitare un confronto tra periodi diversi. Gli importi originari, la valuta, il tasso e la data del cambio sono conservati quando disponibili. Il formato nativo conserva anche l’ordine di assegnazione dei resti: cambiare gli identificativi dei partecipanti nel gruppo di destinazione non sposta i centesimi fra le persone, neppure nel passaggio a una valuta convertita. Le firme interne dei cambi non vengono trasferite.

I CSV neutralizzano i prefissi interpretabili come formule (`=`, `+`, `-`, `@`, anche dopo spazi, controlli o caratteri di formato invisibili, e varianti larghe). L’apostrofo protettivo è codificato in modo reversibile nel CSV Sgancia. Aprire e risalvare un CSV con un foglio elettronico può comunque cambiarne tipi e contenuti: per un trasferimento fedele preferire il JSON.

## Preparare un’importazione

Sono accettati CSV o JSON UTF-8 fino a 2 MB, 500 spese e 200 riferimenti partecipante. PDF, Excel, archivi e formati di altri prodotti non sono importati automaticamente.

1. Scegli il file e premi **Controlla file e associazioni**. Le anteprime non creano spese né pagamenti.
2. Associa ogni riferimento a un partecipante attivo già presente nel gruppo. L’associazione per nome/email non è automatica. I riferimenti originali dello stesso gruppo possono essere riconosciuti per ID. Per aggiungere persone usa prima le impostazioni del gruppo. Non si possono fondere due persone distinte della stessa spesa durante l’importazione.
3. Se necessario indica il nuovo cambio verso la valuta del gruppo e ricalcola l’anteprima. Con valuta di destinazione compatibile viene mantenuto il cambio del file, con data e provenienza dichiarata. Un tasso importato viene etichettato **Importato (tasso dichiarato)**: non è una nuova verifica del tasso storico presso la banca/BCE.
4. Controlla errori, importi, pagatori, quote e pubblico di ogni riga. Il pubblico vuoto/null significa spesa pubblica; una spesa riservata deve includere anche chi importa. I riferimenti mancanti/inattivi non vengono rimossi né riallocati in silenzio.
5. Seleziona le righe valide. I duplicati candidati non sono preselezionati; per includerli serve il comando esplicito **Includi duplicato verificato**. Le origini già importate dallo stesso partecipante non sono importabili una seconda volta. Un file modificato non aggiorna automaticamente le spese già importate: correggerle dall’editor normale. Errori e righe già importate si possono escludere, senza bloccare le altre righe valide.
6. Conferma espressamente le righe selezionate, quindi importa. La conferma ricontrolla permessi, partecipanti, pubblico, valuta e duplicati. Tutte le righe selezionate vengono salvate nella stessa transazione: nessun salvataggio parziale se un controllo fallisce. Ripetere la stessa conferma non crea altre spese.

L’anteprima è cifrata nel database, dura un’ora ed è legata all’account e al suo partecipante nel gruppo. Una nuova anteprima dello stesso account/gruppo sostituisce quella pendente. Dopo la conferma il contenuto completo della bozza viene eliminato, mantenendo soltanto esito/provenienza necessari a riconoscere i duplicati e le spese create. Cambiare la valuta principale richiede una nuova anteprima.

I duplicati economici vengono cercati soltanto fra le spese che puoi vedere e nel file stesso. La provenienza registrata è legata al partecipante autorizzante: non segnala l’esistenza di importazioni riservate agli altri. Due spese legittimamente identiche possono essere incluse dopo verifica esplicita, se hanno riferimenti di origine distinti. Riferimenti di origine ripetuti nel medesimo file sono un errore da correggere.

### CSV semplice

Scarica **Modello CSV semplice**. Usa separatore virgola, UTF-8, data `AAAA-MM-GG`, importi decimali con punto (oppure virgola dentro una cella CSV correttamente quotata).

Colonne obbligatorie: `date`, `title`, `amount`, `paid_by`, `split_between`. In `split_between` separa i riferimenti con `|`: la divisione è in parti uguali e `paid_by` contiene un solo pagatore. Facoltative: `currency`, `exchange_rate`, `category`, `tags`, `audience`, `description`, `source_id`. Tag e pubblico sono separati da `|`; `audience` vuoto rende la spesa pubblica. Per ripartizioni avanzate usa il CSV/JSON nativo Sgancia.

Non modificare campi strutturati/colonne del CSV nativo se vuoi conservarne il round-trip. I valori della colonna `total_minor` sono consultivi: gli importi effettivi vengono sempre ricalcolati e verificati da voci, pagatori e quote.

## Ospiti

Le esportazioni sono **disattivate di default**, anche sui link esistenti. L’amministratore può consentirle quando crea un nuovo link. L’ospite ottiene soltanto la stessa vista pubblica consentita dal link; nomi e dettagli nascosti restano nascosti in tutti e tre i formati. Niente note, tag, identificativi interni, pagamenti, allegati o spese riservate vengono aggiunti al report ospite.

Ogni esportazione riuscita conta come un’apertura e richiede link non revocato/non scaduto, password corretta e aperture disponibili. Un tentativo fallito non consuma l’ultima apertura. Il JSON ospite è un riepilogo consultivo (`sgancia.guest-report/1`), non un formato d’importazione. Con un limite di una sola apertura, dopo aver visualizzato il gruppo potrebbe non restarne una per esportare: scegliere il limite coerente con l’uso desiderato.

## Backup, dati locali e limiti

Le esportazioni non includono file allegati, storia completa, utenti/ruoli, budget, automazioni o configurazione server. Per migrare o ripristinare l’installazione usare il backup cifrato completo, non l’importazione delle spese. I pagamenti e i saldi consultivi esportati **non vengono registrati come nuovi rimborsi** e non annullano né ricreano pagamenti già effettuati.

Il backup completo conserva provenienza e conferme già applicate. Il ripristino revoca tutti i link ospite (da ricreare), annulla le anteprime ancora pendenti e sospende le ricorrenze, così i vecchi comandi non ripartono automaticamente. Prima di una nuova importazione su un database ripristinato, verificare gli eventi successivi alla data del backup.

I file scaricati sono copie sul dispositivo dell’utente: una revoca successiva del link/accesso non può rimuoverle. Condividerli solo con i destinatari appropriati; nessun servizio esterno riceve i contenuti per produrre CSV, JSON o PDF.

## Link ospiti: interruttore globale

Su richiesta dell’utente, i link ospiti sono disattivati di default per l’intera installazione, anche dopo l’aggiornamento di un’istanza esistente. Admin globale → Installazione · link ospiti permette di riattivarli. Sono bloccati creazione, visualizzazione, esportazioni e download ospiti; i link restano conservati e tornano utilizzabili solo se l’admin abilita il servizio e il singolo link è ancora valido/non revocato. Solo un admin globale con identità recente può cambiare l’opzione. Migrazione fd08a762bd12; il blocco 08 della TODO resta da sviluppare.
