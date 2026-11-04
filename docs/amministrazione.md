# Amministrazione

Il ruolo amministratore globale è distinto dai ruoli dei gruppi. Il bootstrap interattivo crea il primo amministratore come superadmin permanente dell’installazione. Non esistono password universali. La chiave globale è un filtro aggiuntivo e non sostituisce l’account personale.

Dal pannello Impostazioni un amministratore può scegliere registrazioni libere, con approvazione, tramite invito o disabilitate; generare inviti di registrazione; attivare utenti in attesa e sospendere account non amministratori. La sospensione revoca le loro sessioni.

La rotazione della chiave globale revoca tutte le concessioni di accesso e tutte le sessioni, inclusa quella che esegue l’operazione. Comunicare la nuova chiave attraverso un canale appropriato prima di riaprire l’accesso. Il segreto non è conservato in chiaro nel database.

Operazioni sensibili richiedono una sessione verificata negli ultimi cinque minuti. Usare “Conferma identità” quando richiesto. L’MFA TOTP cifra il segreto con la chiave dell’installazione; i codici di recupero sono monouso e conservati come hash. Un accesso con passkey richiede la verifica utente del dispositivo ed è alternativo al flusso password+TOTP.

I proprietari/admin di gruppo possono gestire partecipanti e inviti; il ruolo non conferisce accesso a spese segrete dal cui pubblico sono esclusi. Trasferimento proprietà, deleghe ai virtuali e fusioni controllate sono disponibili in Gestione avanzata del gruppo, con le regole di visibilità e i controlli documentati in cronologia-e-membri.md.

Audit essenziale in `audit_events`, senza contenuti delle spese segrete o token. Il pannello Amministrazione e operatività offre audit filtrato, stato dei servizi, politiche e backup con prove di recupero. Le chiavi applicative e di backup richiedono copie di recupero; la rotazione della chiave che cifra TOTP richiederà una procedura dedicata prima della produzione.


## Assegnazione operativa dei ruoli

Impostazioni → Gestione utenti e ruoli globali → **Nomina admin globale** assegna il ruolo di amministratore dell’intera installazione a un account già attivo. **Rimuovi admin globale** lo revoca. L’operazione richiede identità confermata di recente, password dell’amministratore che agisce, codice MFA/recupero se attivo e conferma esplicita del destinatario in UI. Gli utenti sospesi o in attesa devono essere attivati prima della promozione.

Il cambiamento revoca tutte le sessioni dell’account interessato, le challenge passkey pendenti e i token temporanei: serve un nuovo accesso con il nuovo ruolo. Le passkey già registrate restano credenziali valide. Ogni modifica è registrata nell’audit; lo stato atteso impedisce di sovrascrivere un ruolo modificato nel frattempo. Non è possibile rimuovere l’ultimo amministratore globale attivo; la protezione vale anche per richieste contemporanee e non conta gli admin sospesi/in attesa. Gli amministratori globali ordinari possono rinunciare al proprio ruolo se resta un altro admin attivo; l’autorimozione provoca logout. Questa possibilità non riguarda il superadmin fondatore, il cui ruolo è permanente.

Per assegnare esclusivamente il ruolo in un gruppo, aprire **Impostazioni gruppo → Membri → Modifica partecipante → Ruolo nel gruppo → Amministratore del gruppo**. Anche gli inviti indicano esplicitamente “Ruolo nel gruppo”. La promozione globale non cambia Participant.role, non aggiunge l’account a gruppi e non amplia il pubblico delle spese riservate. La revoca globale conserva gli eventuali ruoli amministrativi nei gruppi.


## Superadmin dell’installazione

Il primo account creato da `python -m app.cli init` è il superadmin, sempre amministratore globale attivo. L’identità è registrata in `instance.superadmin_id` tramite riferimento all’ID dell’account, senza dipendere da nome visualizzato o email: rinominare qualcuno con il nome del fondatore non assegna privilegi.

Il fondatore non può essere declassato, sospeso, cancellato o sostituito con un altro account tramite l’app/API. PostgreSQL protegge anche gli aggiornamenti/cancellazioni delle righe interessate con FK e trigger. L’interfaccia mostra “Superadmin · fondatore protetto” e non propone la rimozione del ruolo. Gli altri amministratori globali non possono modificarne nome, email o stato. Il titolare può modificare il proprio nome e gestire password, email e MFA dai percorsi personali autenticati; per la sua email non è disponibile la scorciatoia generica della gestione utenti.

Gli admin globali ordinari restano assegnabili/revocabili. Nessun ruolo globale, superadmin incluso, aggiunge appartenenze ai gruppi o concede accesso alle spese riservate di cui l’account non fa parte. L’uscita da un gruppo riguarda solo la partecipazione a quel gruppo: non cancella l’account né il ruolo di superadmin. Le normali verifiche di login/MFA e la revoca delle sessioni restano attive anche per il fondatore.

Aggiornamento da versione precedente: la migrazione identifica l’unico amministratore iniziale attivo che non risulta nominato tramite la nuova funzione di promozione. Se l’identità è ambigua, si arresta senza assegnazioni arbitrarie: l’operatore del server deve verificare l’ID del fondatore e passarlo in `SGANCIA_LEGACY_SUPERADMIN_ID` al servizio migrate. Il nome/email non vengono usati come scorciatoia. Il riferimento, una volta assegnato, non può essere cambiato dall’ambiente o dall’app. Il downgrade della migrazione su un’installazione inizializzata è bloccato per non rimuovere silenziosamente la protezione.


## Recupero MFA e passkey degli altri utenti
In Gestione utenti e ruoli globali è disponibile Recupera MFA/passkey, con selezione separata dei fattori, conferma dell’identità del titolare, password/MFA dell’operatore e identità recente. Il superadmin e il proprio account sono esclusi dal comando amministrativo; restano i rispettivi comandi personali. Password, email, ruoli e stato del destinatario restano invariati, mentre tutte le sue sessioni e i link temporanei sono revocati. Dettagli e limiti in sicurezza-account.md.

## Funzioni da abilitare

Telegram parte insieme a Sgancia e resta in attesa: configurare token e abilitazione nel pannello globale, quindi Salva e applica. Nessun comando separato. Link ospiti e backup automatici sono inizialmente spenti. SMTP richiede parametri e prova reale; email di notifica anche indirizzo verificato e preferenze. Vedere [operatività](operativita.md) e [roadmap](../ROADMAP.md).

La guida nell’app è accessibile anche prima dell’accesso su /help e non include dati utente. Email dello sviluppatore, repository e donazioni si configurano in backend/app/project_info.py: [dettagli](contatti.md).
