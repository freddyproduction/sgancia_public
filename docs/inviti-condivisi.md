# Link condivisi di registrazione alla piattaforma

In **Impostazioni → Amministrazione → Registrazioni e inviti globali → Link di invito condivisi alla piattaforma**, gli amministratori con permesso Registrazioni possono creare un link non vincolato a una singola email. Gli inviti personali già esistenti rimangono disponibili.

Configura nome, durata in ore o giorni (fino a un anno), massimo utilizzi oppure utilizzi illimitati. Il contatore aumenta solo quando viene creato correttamente un account o una richiesta di approvazione: tentativi errati e account duplicati non consumano utilizzi. La quota è verificata anche per richieste simultanee.

- **Rinnova link** cambia la scadenza, senza azzerare gli utilizzi.
- **Rigenera link** invalida subito il precedente e riparte da zero con un nuovo codice; conserva totale utilizzi e numero di rigenerazioni.
- **Revoca link** blocca le nuove registrazioni senza modificare gli account già creati.
- **Rigenerazione automatica** cambia il codice quando raggiunge il limite: il vecchio link non funziona più, quello nuovo si copia dal pannello. Non prolunga la scadenza. Senza questa opzione, il link viene segnato come esaurito.

Il destinatario apre il link, supera l’eventuale cancello dell’installazione e crea il proprio account. La modalità Con approvazione lascia l’account in attesa; Registrazioni disabilitate blocca anche questi link. Il link non aggiunge a un gruppo e non cambia il ruolo di chi possiede già un account: per i gruppi usa i loro inviti separati.

Il ruolo iniziale è Utente. Solo un superadmin può creare o modificare link che propongono Admin globale o Superadmin, confermando password e MFA/recupero se attivo. Ogni uso del link può assegnare quel ruolo: condividilo privatamente. Un admin globale nuovo parte senza permessi aggiuntivi. In approvazione, un superadmin conferma il ruolo effettivo. Se l’emittente è sospeso, eliminato o perde l’autorizzazione, il link non autorizza nuove registrazioni; quelli privilegiati sono anche legati alla sua versione di sicurezza.
