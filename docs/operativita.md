# Amministrazione operativa — blocco 14

Da Impostazioni → Amministrazione e operatività, riservato agli amministratori globali. Mutazioni sensibili e consultazione audit richiedono identità confermata negli ultimi cinque minuti; usa Conferma identità nella pagina account e ripeti l’azione se necessario. Il ruolo amministratore di un gruppo non basta.

## Politiche

Durata delle nuove sessioni (1–168 ore), email verificata ai nuovi accessi, abilitazione upload e limiti per file/account nel gruppo/numero allegati, scadenza inviti, limiti nuovi link ospiti e conservazione audit. I valori iniziali ereditano i limiti dell’ambiente; il salvataggio crea override nel database senza scrivere `.env`. Le sessioni e gli inviti già emessi mantengono la propria scadenza. Ridurre una quota non elimina file o cronologia. La richiesta di email verificata è consentita solo dopo avere configurato SMTP e verificato l’email dell’operatore; con credenziali corrette viene offerto il percorso di verifica ai nuovi accessi non verificati.

Revoca altre sessioni conserva quella corrente; un amministratore normale non revoca le sessioni del superadmin. L’interruttore della chiave globale e quello ospiti restano controlli separati. Audit 0 significa nessuna eliminazione automatica; se attivata la retention deve essere almeno 7 giorni. Vengono eliminati solo eventi audit, mai ledger/revisioni finanziarie.

## Monitoraggio e privacy

Versione del codice e schema atteso/effettivo, compatibilità, segnali dei servizi automazioni/email/backup, conteggi coda email e ultimi 30 lavori di backup. Un errore backup genera un avviso visibile e un evento amministrativo. I messaggi operativi sono codici generici con spiegazioni, senza errori SMTP/SQL grezzi.

L’audit web mostra gli ultimi 100 eventi di installazione/account/sicurezza, senza attori, risorse, contenuti finanziari o nomi dei gruppi. Non è un accesso ai log grezzi né una deroga alla privacy dei gruppi. `before` consente richieste API per eventi precedenti. Le opzioni sensibili sono protette anche da API, non soltanto nell’interfaccia.

## Backup e prove periodiche

Nuovi servizi Compose `backup-init` e `backup`, nessuna porta aggiuntiva. Il processo web non monta gli archivi e non dispone del socket Docker. Il servizio backup può leggere gli allegati e scrivere solo la cartella riservata `backups/automatic`; le chiavi restano nell’ambiente del container.

Pianificazione inizialmente disattivata. Intervalli 1–168 ore, scadenze allineate UTC, prima esecuzione alla prossima scadenza dopo il salvataggio; controlli circa ogni minuto. Sono recuperati i lavori interrotti e deduplicati quelli dello stesso intervallo. Il lock di processo impedisce due backup contemporanei. Creazione manuale dal pannello richiede conferma e usa lo stesso servizio.

Ogni archivio `.sgb` include dump custom PostgreSQL 17, file immutabili e manifest, autenticati e cifrati AES-GCM. È pubblicato solo dopo verifica completa di cifratura, manifest e file. I temporanei protetti sono su disco in `.scratch`, evitando grandi archivi nella RAM; vengono rimossi normalmente a fine lavoro e i residui abbandonati da oltre 24 ore sono ripuliti dal servizio. Non sono archivi utilizzabili.

Retention da 2 a 365 archivi, applicata dopo un nuovo backup riuscito soltanto ai file del servizio: anche quelli richiesti manualmente dal pannello. I backup CLI in `backups/` restano separati. Una prova fallita non elimina gli archivi precedenti. Mantieni anche una copia fuori da questo server: conservare più archivi sul medesimo disco non protegge dal guasto del disco.

Le prove complete di recupero sono facoltative e richiedono un consenso distinto: primo backup e poi ogni N successi. Decifrano e ripristinano in un database PostgreSQL generato casualmente e separato (`sgancia_probe_…`), controllano ledger e allegati, poi eliminano database e temporanei. Nessun worker/email viene avviato nella copia e il database originale non è sostituito. Serve permesso PostgreSQL di creare database e spazio libero; una mancanza produce un errore nel pannello. Non vengono accettati comandi SQL, nomi database o percorsi arbitrari dal web.

Per esportare un archivio del servizio usando il Docker dell’operatore:

```sh
docker compose cp backup:/app/backups/auto-ID.sgb backups/copia-da-conservare.sgb
```

Sostituisci ID con il nome mostrato nel pannello e conserva chiavi/configurazione separatamente. Gli archivi automatici hanno permessi privati del servizio; non renderli pubblicamente leggibili.

## Telegram e aggiornamenti

Telegram parte insieme a Sgancia e rimane in attesa finché l’admin non abilita l’integrazione dal pannello globale. Token cifrato, modalità polling/webhook, verifica del nome e limite messaggi nel pannello globale. Avvio e collegamento account in `telegram.md`; nessun invio finché non abilitato.

Aggiornamento guidato e recupero sono descritti in `aggiornamenti.md` e `backup-ripristino.md`. Il pannello non scarica o esegue codice. Il runtime include il [client PostgreSQL 17 di Debian Trixie](https://packages.debian.org/trixie/postgresql-client-17); `pg_dump`/`pg_restore` non richiedono installazioni sul Mac/host.

## Prove e limiti

111 test mirati PostgreSQL, controllo schema upgrade/check/downgrade, altri 9 test operativi finali e 15 frontend. Backup cifrato con immagine sintetica e ripristino isolato realmente eseguiti. UI: politiche, backup verificato e associazione con anteprima. Script update e restore completi su Compose QA: identità e ledger conservati. SMTP esterno e installazione server Linux/Nginx/Cloudflare reali restano verifiche dei blocchi 04/15; nessun dato o account reale usato per QA.

Chiave ricordata e login hanno ora [durate indipendenti configurabili](durate-accesso.md). Il logout personale conserva la chiave verificata; il modulo di accesso permette di dimenticarla esplicitamente. Modalità browser oppure minuti/ore/giorni/mesi/anni per i nuovi accessi; verifica recente delle operazioni sensibili invariata.
