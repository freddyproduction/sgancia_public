# Registrazioni e inviti globali

Disponibile agli amministratori globali in **Impostazioni → Registrazioni e inviti globali**. La gestione non assegna ruoli di gruppo né privilegi globali agli invitati. Gli inviti combinati account + gruppo si gestiscono nelle impostazioni del relativo gruppo; questa schermata elenca gli inviti di sola registrazione.

## Modalità e richieste in attesa

La modalità corrente viene letta dal server, non presunta dal modulo. Libere, con approvazione, solo con invito o disabilitate si salvano esplicitamente. Il controllo della versione della policy impedisce di sovrascrivere il cambiamento di un altro amministratore. Il refresh non sovrascrive una scelta già modificata.

Con approvazione, anche una registrazione con invito crea un account in attesa. Nella coda dedicata cercare nome/email, controllare lo stato di verifica email e scegliere Approva oppure Rifiuta richiesta, quindi confermare nel popup. Approva rende l’account attivo senza promuoverlo. Rifiuta lo sospende, conservando account e storico: può essere riattivato nella gestione utenti. Non vengono inviate email automaticamente da queste operazioni. Il cambio di modalità non approva o rifiuta le richieste già presenti. Una richiesta già gestita non può essere sovrascritta con una decisione basata sulla vecchia schermata.

## Inviti

- **Crea:** email destinatario e durata da 1 a 90 giorni (predefinita 7). Email normalizzata, account esistenti e inviti globali attivi duplicati segnalati.
- **Stato:** attivo, scaduto, utilizzato o revocato; ricerca per email, filtro stato e paginazione. I vecchi inviti senza data di creazione rimangono validi secondo stato/scadenza; la migrazione assegna un ID senza cambiare il codice.
- **Rinnova durata:** imposta la nuova scadenza a partire da adesso; conserva il codice condiviso. Può riattivare uno scaduto non usato né revocato, purché non esista un altro invito attivo per la stessa email. Non permette di recuperare il codice in chiaro.
- **Rigenera codice:** revoca il precedente e crea un nuovo invito per la stessa email, con nuova durata. Copiare e condividere il nuovo link. Anche un invito revocato può essere sostituito; un utilizzato non può creare un secondo account.
- **Rimuovi / revoca:** invalida subito il codice e lo toglie dagli attivi. Il record resta consultabile tra i revocati e nell’audit; nessun account viene cancellato.

Il codice e il link vengono restituiti soltanto al momento della creazione o rigenerazione. Nel database si conserva l’hash, non un codice recuperabile. Se perdi il link rigenera; se lo hai già condiviso e vuoi solo prolungarne la validità rinnova. Il link usa il frammento URL; condividilo privatamente e non allegarlo a issue o log. Non viene spedito automaticamente.

Le operazioni richiedono una verifica recente dell’identità; se necessaria si apre il popup dell’account. Dopo la conferma ripetere esplicitamente l’operazione. Versioni attese, lock installazione e transazioni impediscono rinnovi/rigenerazioni concorrenti incompatibili e corse con consumo o revoca. Un invito non supera il cancello globale, la verifica email richiesta, la modalità approvazione o il blocco delle registrazioni.

Il backup comprende la metadata degli inviti. Il ripristino invalida i non consumati come revocati e mantiene i già usati non riutilizzabili. Le vecchie versioni di backup senza metadata conservano la precedente invalidazione tramite used. Non fare downgrade su inviti revocati/rinnovati: la migrazione rifiuta la perdita di quei controlli.

## Aggiornamento ruoli globali

Le descrizioni storiche del fondatore permanente sono sostituite dalla [gestione aggiornata dei superadmin e dei permessi](ruoli-globali.md): più superadmin, revoca soltanto da parte di un altro, protezione dell’ultimo e account conservato. Solo i superadmin assegnano ruoli privilegiati negli inviti/approvazioni o modificano capacità degli admin.
