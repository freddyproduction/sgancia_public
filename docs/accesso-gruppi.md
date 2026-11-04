# Entrare in un gruppo, associare una persona, vedere come ospite

**Membro:** usa un account personale ed entra con un ruolo (membro, amministratore del gruppo o visualizzatore). **Persona senza account:** ha già spese e saldi ma non un login; un invito nominativo può collegarla al suo account conservando lo stesso identificativo. **Ospite:** apre un link separato di sola lettura e non diventa membro.

## Percorso del destinatario

Accedi al tuo account → Ho un invito oppure Associa partecipante. Incolla un codice o il link completo della stessa installazione. L’anteprima verifica tipo, email destinatario, scadenza, gruppo attivo e persona disponibile, e mostra gruppo, ruolo e nome da collegare. Conferma solo se corrispondono a te. Se sei già membro, puoi aprire il gruppo senza duplicarti. Un codice può essere usato una volta; il tentativo ripetuto dallo stesso account già associato non crea una seconda persona.

Per registrarsi da zero serve un invito Nuovo account + gruppo, emesso da un amministratore globale che gestisce anche il gruppo, destinato alla propria email. Un invito per account esistenti non scavalca la politica di registrazione dell’installazione. Se hai già un account, scegli Accedi: non registrarne un altro.

## Percorso del gestore

Impostazioni gruppo → Inviti e ospiti. Scegli account esistente oppure nuovo account + gruppo (quest’ultimo solo se autorizzato globalmente), email e ruolo. Se la persona è già presente senza account, selezionala esplicitamente: conserverà spese, saldi e pubblico. Non selezionarla per una persona diversa. Non si può prendere l’account già collegato di qualcun altro; se esistono duplicati serve una fusione controllata, non un’associazione per nome.

Condividi privatamente il link o codice generato. Il server conserva solo il digest, non permette di recuperare il codice originale. L’elenco Inviti membri creati permette di vedere scadenza/stato e revocare quelli inutilizzati. Se il gestore dei nuovi inviti esce, viene sospeso o perde i permessi, i codici diventano inutilizzabili. La registrazione di nuovi account non resta autorizzata se l’emittente perde il ruolo globale. I vecchi codici anteriori a questo aggiornamento senza emittente registrato restano validi fino a scadenza/revoca: il gestore può revocarli e generarne di nuovi.

I codici di associazione già esistenti continuano a funzionare nello stesso modulo, dopo verifica dell’email dell’account e della disponibilità della persona. Per creare un nuovo account collegato usare invece l’invito completo email-bound.

## Link ospiti

Restano disabilitati globalmente per default, anche in questa consegna. Solo l’amministratore globale può abilitarli; il gestore del gruppo decide poi ogni link, durata, password, aperture, nomi/dettagli/allegati/export. Il link non rende pubblico il gruppo a chi non lo possiede. Limiti di installazione non attivano il servizio da soli. Solo spese pubbliche autorizzate; nessuna associazione di account e nessun comando di modifica. Allegati/export mantengono i controlli già previsti.

Incollare un link ospite nel modulo membri mostra Apri come ospite e non esegue l’accettazione di un invito. Link di un’altra installazione o URL con credenziali vengono rifiutati. I token restano nel frammento URL, non nei log di query. Revoca, scadenza, gruppo non disponibile e interruttore globale vengono controllati anche dalle API.

Un recupero da backup revoca link ospiti e vecchi inviti/associazioni e disattiva gli ospiti globalmente, impedendo il ritorno di autorizzazioni già revocate. I membri già collegati conservano identità e dati; i gestori possono emettere nuovi inviti dopo il controllo.
