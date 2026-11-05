# Superadmin e permessi degli admin globali

Queste regole sostituiscono la precedente protezione permanente del solo fondatore, su richiesta esplicita del titolare. Il primo account resta superadmin all’aggiornamento. Possono esistere più superadmin, e soltanto un altro superadmin può revocare quel ruolo: la sola revoca del ruolo non cancella account, gruppi e conti. L’ultimo superadmin attivo è protetto anche a livello database.

## Ruolo e permessi

In Impostazioni → Gestione utenti e ruoli globali, il superadmin apre **Ruolo e permessi**. Può scegliere Utente, Admin globale o Superadmin. Per un admin globale può assegnare separatamente account ordinari/recupero fattori, registrazioni/inviti/approvazioni, SMTP, cancello/chiave, politiche, ospiti, Telegram, backup, audit e revoca sessioni. Ruoli e pubblici dei gruppi restano indipendenti: neppure il superadmin ottiene la visibilità delle spese da cui è escluso.

I superadmin hanno tutte le capacità della piattaforma. I nuovi admin globali creati dal percorso aggiornato partono senza permessi aggiuntivi; il superadmin li abilita esplicitamente. Gli admin esistenti mantengono le precedenti capacità operative fino alla personalizzazione, ma non possono più nominare amministratori o superadmin. Le nomine globali sono riservate ai superadmin anche tramite API.

Il salvataggio richiede identità recente, password personale del superadmin e MFA/recupero se attivo, conferma esplicita e versione attesa del destinatario. I cambiamenti revocano le sessioni del destinatario. L’interfaccia nasconde i controlli non concessi e il server verifica i permessi per ogni richiesta. Non basta modificare il frontend o chiamare un endpoint direttamente. Gli admin ordinari non possono modificare o recuperare altri amministratori, né revocare sessioni dei superadmin. I fattori di un superadmin restano gestibili soltanto personalmente o tramite il recupero locale previsto, non da altri utenti.

La revoca di un ruolo non interrompe i backup già autorizzati e accodati. I permessi si applicano alle nuove richieste; pianificazioni e lavori preesistenti conservano il comportamento documentato. Delegare SMTP, accesso o backup è una scelta di fiducia sul funzionamento dell’installazione, non soltanto la visualizzazione di un pulsante.

## Inviti e approvazioni

Il superadmin può scegliere Utente, Admin globale o Superadmin durante la creazione di un invito globale. Le nomine privilegiate richiedono nuovamente password e MFA del superadmin. Gli inviti personali restano legati all’email e monouso; sono disponibili anche link condivisi per più account con scadenza, quota e rigenerazione (vedi inviti-condivisi.md). Per inviti privilegiati si verifica anche che l’emittente sia ancora superadmin attivo e che la sua versione di sicurezza corrisponda: dopo variazioni di sicurezza o revoche può servire un nuovo invito autorizzato.

In modalità approvazione, la registrazione resta **in attesa e senza privilegi**, anche se l’invito propone superadmin. Alla conferma un superadmin sceglie il ruolo effettivo e fornisce la prova aggiuntiva per ruoli elevati. Gli admin delegati alle registrazioni approvano soltanto richieste ordinarie. Nessun invito aggira le registrazioni disabilitate, la chiave installazione o le regole di verifica email. Gli inviti account + gruppo restano nel percorso del gruppo e non assegnano autorità globale.

## Migrazione e recupero

Migrazione f518a762bd19: conserva il primo superadmin e i permessi precedenti degli admin esistenti; aggiunge autorità multiple, capacità per admin e ruoli richiesti negli inviti/approvazioni. Il riferimento instance.superadmin_id diventa l’ancora di un superadmin attivo; se quel ruolo viene revocato legittimamente passa a un altro superadmin. Il nome visualizzato non determina il ruolo. Audit conserva le decisioni; non sono inseriti password, codici o token nel registro.

Backup e ripristino conservano ruoli e capacità; il restore continua a revocare sessioni/inviti sensibili e sospendere automatismi. Un downgrade che perderebbe superadmin aggiuntivi, richieste privilegiate o permessi personalizzati viene rifiutato. Non usare SQL manuale per aggirare la protezione dell’ultimo superadmin.

## Sospensione ed eliminazione

Un superadmin può sospendere o eliminare anche un altro superadmin, con conferma password/MFA e mantenendo almeno un superadmin attivo. La sospensione conserva il ruolo; l’eliminazione anonimizza l’account e preserva la contabilità. Non si può intervenire sul proprio account da questi controlli. Vedi [eliminazione account](eliminazione-account.md).
