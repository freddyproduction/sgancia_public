# Account, email, MFA e recupero

## Impostazioni personali

La pagina Impostazioni contiene email/verifica, cambio email e password, autenticazione a due fattori, passkey, sessioni e metodi di pagamento. Il ruolo di amministratore globale della piattaforma è distinto dai ruoli proprietario/amministratore dei gruppi. Il primo account del bootstrap è il superadmin fondatore permanente: non può essere declassato, sospeso o eliminato tramite l’app/API; gli altri admin non possono modificarne l’account. Un amministratore di gruppo non accede a impostazioni SMTP, gate, registrazioni o utenti dell’installazione.

Il cambio password richiede quella attuale e, se attiva, la verifica MFA; mantiene la sessione corrente e revoca le altre. I token temporanei e le richieste passkey pendenti vengono invalidati. Le sessioni hanno anche una versione di autenticazione confrontata con l’account, per impedire che sessioni emesse contemporaneamente a una revoca tornino valide con la vecchia versione. Le passkey già registrate restano metodi validi fino alla loro revoca esplicita.

## Autenticazione a due fattori

Il TOTP è compatibile con Google Authenticator e altre app standard. Configurare una chiave basata sul tempo usando il segreto mostrato privatamente oppure il collegamento locale otpauth. Il segreto non viene mandato a servizi esterni per generare QR. Confermare con il codice dell’app e conservare i dieci codici di recupero, ciascuno monouso; nel DB sono presenti solo i loro hash.

Per disattivare MFA o rinnovare i codici di recupero occorrono password e un codice MFA/recupero valido. Le altre sessioni sono revocate; il rinnovo invalida tutti i precedenti codici. Per cambiare autenticatore, avviare la rotazione e confermare il codice del nuovo autenticatore insieme alla password: quello precedente resta valido fino alla conferma. I codici TOTP già utilizzati non sono riutilizzabili: attendere il prossimo codice oppure usare un codice di recupero ancora valido.

Non comunicare password, segreti TOTP o codici di recupero in chat o negli screenshot.

## Verifica email e recupero via posta

Gli account esistenti restano utilizzabili dopo l’aggiornamento e iniziano con email da verificare. La verifica è richiesta per condividere i metodi di pagamento e per ricevere link di recupero password via email. Non viene imposta retroattivamente per leggere o modificare le normali spese autorizzate.

Con l’invio email configurato, la registrazione accoda la verifica; nelle impostazioni è disponibile il reinvio, limitato a tre richieste in cinque minuti. Link di verifica validi 24 ore, di recupero validi 30 minuti. Sono monouso, legati a indirizzo, account, finalità e versione di autenticazione; reinvio, cambio email o modifica delle credenziali invalidano i precedenti. Il cambio email richiede password/MFA e revoca le altre sessioni; anche un cambio da amministrazione azzera la verifica. La verifica email non crea una sessione di login.

I link usano l’origine principale dell’installazione e un token nel frammento, rimosso dalla barra degli indirizzi prima dell’interazione. Non modificano dati tramite una semplice richiesta GET: l’utente conferma nella pagina. Il recupero non rivela se un indirizzo esiste e richiede ancora il codice MFA/recupero se attivo. Un link email, da solo, non disattiva MFA. Dopo il recupero tutte le sessioni vengono revocate.

## SMTP da interfaccia web

Solo l’amministratore globale trova **Impostazioni → Impostazioni dell’installazione → Invio email SMTP**. Compilare host, porta, sicurezza STARTTLS o TLS diretto, email mittente e, se richiesti, nome utente/password. Abilitare l’invio e salvare. Le credenziali vengono cifrate con la chiave applicativa; la password non è restituita dalle API, inclusi gli errori di validazione. Lasciarla vuota per conservare quella già salvata, oppure usare l’opzione esplicita per eliminarla.

La configurazione web prevale sui parametri SGANCIA_SMTP_* iniziali dell’ambiente. Modifiche protette da identità confermata negli ultimi cinque minuti e audit; vengono lette dal servizio Compose `mail` senza riavvio. Il certificato TLS deve essere valido; non sono disponibili modalità di autenticazione in chiaro o scorciatoie che ignorino la verifica del certificato.

“Invia email di prova al mio account” accoda esclusivamente un messaggio verso l’indirizzo dell’amministratore corrente. La pagina mostra conteggi di messaggi in attesa/falliti. Il servizio prova nuovamente gli errori temporanei con attesa crescente, per un massimo di otto tentativi e comunque entro la scadenza. Un messaggio superseduto da un nuovo token non viene inviato se è ancora in coda. I log non contengono destinatari, password, contenuti o link. Una conferma SMTP seguita da un arresto prima del commit può produrre una consegna duplicata; il link resta monouso.

Senza SMTP completo/abilitato nessuna email parte e la UI lo indica. Il servizio `mail` deve essere avviato nello stesso Compose; `docker compose up -d` lo include. La prova deve arrivare davvero in casella prima di considerare verificata l’integrazione con il proprio fornitore. Controllare anche spam e l’origine principale configurata per i link. Non sono stati inseriti credenziali o recapiti SMTP reali nel progetto.

## Recupero locale senza posta

Un operatore che controlla il server può eseguire, dopo verifica manuale dell’identità:

```sh
docker compose exec api python -m app.recover
```

Il comando interattivo chiede conferma della verifica d’identità ed email, revoca le sessioni e genera un link privato di 30 minuti da consegnare esclusivamente al titolare. Non richiede un servizio cloud e non stampa password esistenti. Il reset conserva MFA; se sono stati persi anche tutti i fattori, usare consapevolmente `python -m app.recover --reset-mfa`: richiede una seconda conferma, revoca TOTP, codici di recupero e passkey, poi genera il nuovo link. L’operazione è tracciata. Chi controlla il server e le chiavi ha già autorità sui dati dell’installazione: questa procedura non è disponibile come endpoint web o comando di un amministratore di gruppo.

## Gate opzionale

La chiave globale iniziale è abilitata di default. Solo l’admin globale può abilitarla/disabilitarla dalla sezione Accesso all’installazione, con identità recente e conferma esplicita. Entrambi i cambi revocano tutte le sessioni e concessioni, compresa quella dell’admin. Disabilitarla salta solo il primo passaggio: password/passkey, MFA, ruoli, CSRF e controllo delle origini restano attivi.

La riattivazione richiede conoscere la chiave già configurata; la rotazione della chiave rimane una funzione separata. Recupero operativo locale: `docker compose exec api python -m app.recover --enable-gate` riabilita il gate senza modificare la chiave e revoca gli accessi. Non disabilitare il gate dell’istanza in uso per fare prove automatiche.

## Prove passkey su Mac e iPhone — da svolgere dal titolare

L’utente ha indicato Mac e iPhone come dispositivi di prova. La presenza di una firma verificata nei test automatici non equivale a una prova con hardware reale.

1. Aprire l’origine principale configurata per l’installazione. Mac: HTTPS o localhost possono essere contesti sicuri; un alias differente dall’origine principale viene comunque rifiutato dal server. iPhone: usare il dominio HTTPS con certificato valido; l’IP LAN in HTTP non supporta questo percorso.
2. In Impostazioni → Passkey, scegliere Aggiungi passkey e completare personalmente la conferma con impronta, volto o PIN. Non delegare l’inserimento di credenziali reali all’agente.
3. Provare l’accesso da una seconda sessione mantenendo un accesso di riserva, poi ripetere su iPhone tramite l’origine HTTPS principale.
4. Rimuovere la passkey di prova e controllare che non possa più essere usata. La rimozione revoca le altre sessioni e le richieste pendenti; la sessione corrente rimane aperta.
5. Annotare esiti per entrambi i dispositivi, inclusi annullamento del dialogo, origine errata e revoca. Non segnare conclusa la voce hardware prima di questi esiti.

Nessuna passkey reale è stata creata/rimossa dall’agente e nessuna password/MFA reale è stata modificata durante lo sviluppo.


## Comandi visibili per rimuovere i fattori

**Personale:** Impostazioni → Email e sicurezza account → MFA: disattiva o modifica → Disattiva MFA, disponibile quando TOTP è attivo. Confermare password e codice MFA/recupero; cancella anche configurazioni pendenti e codici di recupero, revoca le altre sessioni e mantiene valide le passkey esistenti.

**Personale, passkey:** Impostazioni → Passkey: aggiungi o rimuovi → Rimuovi passkey → Conferma rimozione passkey. Ogni chiave è revocabile singolarmente, anche fino a rimuoverle tutte. Richiesta identità recente; se scaduta, usare Conferma identità. La sessione corrente resta aperta, le altre e le challenge pendenti vengono revocate; MFA rimane attiva se non disabilitata separatamente. Sgancia revoca il collegamento server: l’eventuale voce salvata nel gestore password del dispositivo può essere cancellata anche da lì.

**Recupero da admin globale:** Impostazioni → Gestione utenti e ruoli globali → Recupera MFA/passkey. Disponibile solo sugli altri account, mai sul superadmin. Selezionare se disattivare MFA (compresi pending/recovery), cancellare tutte le passkey o entrambi. Confermare la verifica dell’identità del titolare e fornire password e MFA dell’amministratore che opera, con sessione verificata di recente. Non è richiesta la disponibilità del fattore perso del destinatario.

L’azione revoca tutte le sessioni, challenge e link temporanei del destinatario; password, email, stato e ruoli non cambiano. Un account sospeso resta sospeso. Al successivo accesso servono password e gli eventuali fattori conservati. Operazione tracciata nell’audit per ogni tipo di fattore selezionato e limitata a cinque richieste ogni cinque minuti per admin. Non crea sessioni di accesso per l’operatore e non restituisce password, segreti o codici del destinatario.

Il superadmin non può usare né subire questa scorciatoia amministrativa: gestisce i propri fattori dai percorsi personali. In caso di perdita totale resta la procedura locale del server dopo verifica manuale dell’identità, distinta dai privilegi web.

## Popup di conferma identità

Quando un’operazione richiede una verifica recente compare automaticamente un popup sopra la pagina corrente. Inserire la password del proprio account, non la chiave globale, e il codice MFA/recupero se attivo. Gli errori restano nel popup. Dopo il successo premere Torna all’operazione e ripetere esplicitamente il comando dal modulo: nessuna azione sensibile viene ripetuta automaticamente. Annulla chiude il popup senza verificare l’identità e senza eseguire l’operazione.

Chiave ricordata e login hanno ora [durate indipendenti configurabili](durate-accesso.md). Il logout personale conserva la chiave verificata; il modulo di accesso permette di dimenticarla esplicitamente. Modalità browser oppure minuti/ore/giorni/mesi/anni per i nuovi accessi; verifica recente delle operazioni sensibili invariata.
