# Amministrazione

Il ruolo amministratore globale è distinto dai ruoli dei gruppi. La configurazione web (o il bootstrap CLI alternativo) crea il primo account come superadmin; il ripristino iniziale `.sgp` recupera quelli originali senza crearne un altro. Non esistono password universali. La chiave globale è un filtro aggiuntivo e non sostituisce l’account personale.

Dal pannello Impostazioni un amministratore può scegliere registrazioni libere, con approvazione, tramite invito o disabilitate; generare inviti di registrazione; attivare utenti in attesa e sospendere account non amministratori. La sospensione revoca le loro sessioni.

La rotazione della chiave globale revoca tutte le concessioni di accesso e tutte le sessioni, inclusa quella che esegue l’operazione. Comunicare la nuova chiave attraverso un canale appropriato prima di riaprire l’accesso. Il segreto non è conservato in chiaro nel database.

Operazioni sensibili richiedono una sessione verificata negli ultimi cinque minuti. Usare “Conferma identità” quando richiesto. L’MFA TOTP cifra il segreto con la chiave dell’installazione; i codici di recupero sono monouso e conservati come hash. Un accesso con passkey richiede la verifica utente del dispositivo ed è alternativo al flusso password+TOTP.

I proprietari/admin di gruppo possono gestire partecipanti e inviti; il ruolo non conferisce accesso a spese segrete dal cui pubblico sono esclusi. Trasferimento proprietà, deleghe ai virtuali e fusioni controllate sono disponibili in Gestione avanzata del gruppo, con le regole di visibilità e i controlli documentati in cronologia-e-membri.md.

Audit essenziale in `audit_events`, senza contenuti delle spese segrete o token. Il pannello Amministrazione e operatività offre audit filtrato, stato dei servizi, politiche e backup con prove di recupero. Le chiavi applicative e di backup richiedono copie di recupero; la rotazione della chiave che cifra TOTP richiederà una procedura dedicata prima della produzione.


## Assegnazione operativa dei ruoli

Solo un superadmin può aprire **Impostazioni → Gestione utenti e ruoli globali → Ruolo e permessi**, scegliere Utente/Admin globale/Superadmin e personalizzare le capacità dell’admin. Servono identità recente, password personale, MFA se attiva e conferma esplicita. Gli account non attivi devono essere prima approvati o attivati.

Le modifiche revocano le sessioni del destinatario e conservano identità, gruppi e conti. La versione attesa impedisce aggiornamenti concorrenti incompatibili. Un superadmin non può revocarsi il ruolo da solo: serve un altro superadmin; l’ultimo rimane protetto. Gli admin globali ordinari non assegnano ruoli o permessi.

Per assegnare esclusivamente il ruolo in un gruppo, aprire **Impostazioni gruppo → Membri → Modifica partecipante → Ruolo nel gruppo → Amministratore del gruppo**. Anche gli inviti indicano esplicitamente “Ruolo nel gruppo”. La promozione globale non cambia Participant.role, non aggiunge l’account a gruppi e non amplia il pubblico delle spese riservate. La revoca globale conserva gli eventuali ruoli amministrativi nei gruppi.


## Superadmin dell’installazione

Il primo account creato dalla configurazione web o dalla CLI `python -m app.cli init` è superadmin. La migrazione conserva questo ruolo. L’installazione può avere più superadmin, identificati tramite ID e attributi di autorità, non nome o email. Un altro superadmin può revocare il ruolo del primo senza cancellarne l’account. Il riferimento `instance.superadmin_id` mantiene un superadmin attivo e passa a un altro quando necessario. FK, vincoli e trigger proteggono il riferimento e l’ultimo superadmin.

Gli admin globali ordinari restano assegnabili/revocabili. Nessun ruolo globale, superadmin incluso, aggiunge appartenenze ai gruppi o concede accesso alle spese riservate di cui l’account non fa parte. L’uscita da un gruppo riguarda solo la partecipazione a quel gruppo: non cancella l’account né il ruolo di superadmin. Le normali verifiche di login/MFA e la revoca delle sessioni restano attive anche per il fondatore.

Aggiornamento da versione precedente: la migrazione identifica l’unico amministratore iniziale attivo che non risulta nominato tramite la nuova funzione di promozione. Se l’identità è ambigua, si arresta senza assegnazioni arbitrarie: l’operatore del server deve verificare l’ID del fondatore e passarlo in `SGANCIA_LEGACY_SUPERADMIN_ID` al servizio migrate. Il nome/email non vengono usati come scorciatoia. L’ambiente non riassegna un riferimento già configurato; l’app può trasferirlo a un altro superadmin attivo durante le operazioni autorizzate, preservando la protezione dell’ultimo. Il downgrade della migrazione su un’installazione inizializzata è bloccato per non rimuovere silenziosamente la protezione.


## Recupero MFA e passkey degli altri utenti
In Gestione utenti e ruoli globali è disponibile Recupera MFA/passkey, con selezione separata dei fattori, conferma dell’identità del titolare, password/MFA dell’operatore e identità recente. Il superadmin e il proprio account sono esclusi dal comando amministrativo; restano i rispettivi comandi personali. Password, email, ruoli e stato del destinatario restano invariati, mentre tutte le sue sessioni e i link temporanei sono revocati. Dettagli e limiti in sicurezza-account.md.

## Funzioni da abilitare

Telegram parte insieme a Sgancia e resta in attesa: configurare token e abilitazione nel pannello globale, quindi Salva e applica. Nessun comando separato. Link ospiti e backup automatici sono inizialmente spenti. SMTP richiede parametri e prova reale; email di notifica anche indirizzo verificato e preferenze. Vedere [operatività](operativita.md) e [roadmap](../ROADMAP.md).

La guida nell’app è accessibile anche prima dell’accesso su /help e non include dati utente. Email dello sviluppatore, repository e donazioni si configurano in backend/app/project_info.py: [dettagli](contatti.md).

Inviti di sola registrazione e coda di approvazione: [gestione globale](inviti-globali.md), con stato, durata, rinnovo, rigenerazione, revoca e conferme. Gli inviti account + gruppo restano distinti.

Chiave ricordata e login hanno ora [durate indipendenti configurabili](durate-accesso.md). Il logout personale conserva la chiave verificata; il modulo di accesso permette di dimenticarla esplicitamente. Modalità browser oppure minuti/ore/giorni/mesi/anni per i nuovi accessi; verifica recente delle operazioni sensibili invariata.

## Aggiornamento ruoli globali

Le descrizioni storiche del fondatore permanente sono sostituite dalla [gestione aggiornata dei superadmin e dei permessi](ruoli-globali.md): più superadmin, revoca soltanto da parte di un altro, protezione dell’ultimo e account conservato. Solo i superadmin assegnano ruoli privilegiati negli inviti/approvazioni o modificano capacità degli admin.

## Inviti condivisi e account

Oltre agli inviti personali sono disponibili [link condivisi](inviti-condivisi.md) con durata, quota, revoca e rigenerazione. Solo i superadmin gestiscono [sospensione ed eliminazione a ogni livello](eliminazione-account.md), proteggendo l’ultimo superadmin attivo e conservando la contabilità condivisa.


[Backup portabili, parametri gruppi e ripristino iniziale](backup-portabile.md). [Amici](amici.md).
