# Backup e ripristino

La procedura copre PostgreSQL (identità, revisioni, contabilità, preferenze e immagini gruppo) **e i file privati delle spese/ricevute**, comprese anteprime e allegati rimossi ancora recuperabili. Database e file sono raccolti in un bundle con manifest e digest, poi cifrati con autenticazione.

Configurare `SGANCIA_BACKUP_KEY` con una chiave casuale base64 di 32 byte, diversa da `SGANCIA_ENCRYPTION_KEY`. Conservare una copia di entrambe al di fuori del server: il dump del database non contiene le chiavi applicative. Non inviare chiavi nelle chat o nei log.

```sh
scripts/backup.sh
```

Il backup usa `pg_dump -Fc`, aggiunge i file immutabili riferiti dai metadati e cifra il bundle a blocchi autenticati AES-256-GCM con sequenza e record finale e viene pubblicato con rinomina solo se tutta la pipeline riesce. File in `backups/`, permessi privati e esclusione da Git. I file incompleti non sono backup validi. Eseguire copie su un supporto distinto e definire retention secondo l’installazione.

Ripristino: prima fare una copia di sicurezza dello stato attuale. Il comando sostituisce lo schema/dati del database corrente e richiede conferma esplicita tramite argomento.

```sh
docker compose stop api mail worker backup
scripts/restore.sh backups/NOME.sgb --confirm-restore
docker compose run --rm --no-deps migrate
docker compose start api mail worker
```

La decifratura viene interamente autenticata prima di modificare il database. Il bundle viene validato integralmente (nomi ammessi, dimensioni, digest, file mancanti/duplicati e divieto di link/percorso esterno) prima di pubblicare i blob ripristinati. I file immutabili vengono pubblicati prima del ripristino DB: se pg_restore fallisce, la transazione DB viene annullata e possono restare soltanto file non referenziati, senza sovrascrivere contenuti diversi già esistenti. Il dump temporaneo in `.local/` è privato e rimosso all’uscita; `pg_restore` opera in una sola transazione e si ferma agli errori. Una chiave sbagliata o un file alterato/incompleto impediscono il ripristino. Mantenere la chiave TOTP originaria dopo il ripristino.

La pianificazione e la retention si configurano da Admin globale → Backup automatici e prove di recupero. Il servizio backup è incluso in Compose e rimane senza pianificazione finché non viene abilitato. Le prove automatiche richiedono consenso e usano un database temporaneo separato. Copiare comunque i backup cifrati su una destinazione esterna protetta: il solo disco del server non è un backup sufficiente.

Verifica locale effettuata: backup cifrato e ripristino tramite gli script su istanza di prova con una spesa; conteggio ripristinato e login/sessione verificati dopo riavvio. Non equivale a una prova di disaster recovery dell’infrastruttura del server.

Le immagini dei gruppi restano nel DB; i file delle spese/rimborsi sono nel volume privato. L’invariante di coerenza è: blob pubblicato atomicamente prima del commit dei metadati e nessuna rimozione fisica nel normale utilizzo. Perciò ogni metadato nello snapshot pg_dump ha un file disponibile alla raccolta successiva. Gli upload successivi al dump possono aggiungere file extra, senza riferimenti mancanti. File mancanti o blob con digest errato fanno fallire il backup prima della pubblicazione del file finale.

Compatibilità: i vecchi backup cifrati contenenti il solo dump PostgreSQL sono ancora riconosciuti. Ripristinando una versione precedente, applicare le migrazioni compatibili prima di riavviare l’API; non collegare codice nuovo a uno schema vecchio. Non si possono ricostruire file che non erano inclusi in un backup legacy.

Verifica del 3 novembre 2026: scripts/backup.sh e restore.sh usati con un progetto Docker QA separato, senza porte pubblicate. Dopo upload di un’immagine e backup, sono stati eliminati schema e blob soltanto del QA. Il ripristino ha recuperato metadati, file con hash identico, login e saldi. Il progetto QA è stato rimosso al termine. Gli errori di contenuto/hash e i percorsi pericolosi sono coperti anche dai test automatici. Nessun ripristino distruttivo è stato eseguito sull’istanza in uso.


Dal blocco 04 il backup comprende anche metodi di pagamento, immagini personali e configurazione SMTP cifrata nel DB. Il ripristino richiede entrambi i servizi api e mail arrestati. Dopo pg_restore lo script elimina sessioni, concessioni del gate, challenge passkey, token email/recupero e coda email: non riattiva vecchi accessi o link già spediti. Applicare le migrazioni prima di riavviare api e mail.

Dal blocco 05 il ripristino sospende tutte le ricorrenze (`restore_review`). Controllare modelli e spese prima della riattivazione esplicita; i lavori conclusi conservano il riferimento alla spesa e non vengono rieseguiti. Vedi [modelli e ricorrenze](modelli-ricorrenze-anticipi.md).

Dal blocco 07 il ripristino elimina le anteprime di importazione pendenti, mantenendo gli esiti applicati e la provenienza per il controllo duplicati. Le esportazioni CSV/JSON/PDF non sostituiscono questo backup completo.

Dal blocco 07 tutti i link ospite ripristinati vengono revocati, per impedire che un backup precedente faccia tornare validi link o permessi export già revocati. Generare nuovi link dopo il ripristino.


## Backup pianificati e recupero periodico (blocco 14)

Il pannello globale controlla il servizio `backup`, inizialmente senza pianificazione attiva. Gli archivi web/periodici sono in `backups/automatic`; il servizio `backup-init` prepara solo questa directory riservata. I backup CLI restano nella cartella principale e non sono soggetti alla retention del servizio. Dettagli, esportazione, integrità e prove complete nel database temporaneo sono in `operativita.md`.

La prova periodica non richiama lo script di ripristino sul database corrente: crea una copia separata e la elimina dopo aver verificato DB, ledger e allegati. Lo script di ripristino dell’installazione, invece, è deliberatamente distruttivo e richiede backup corrente, servizi fermi (incluso backup), codice compatibile e conferma esplicita. API/worker/email non vengono avviati nella copia di prova.

Dopo un recupero completo: backup pianificati e ricorrenze sospesi; lavori pendenti marcati da rivedere; notifiche sospese/coda email svuotata; sessioni, gate grant, passkey di installazione e challenge revocati; inviti/associazioni/link ospiti invalidati e ospiti globalmente spenti. Dati e identità dei membri già associati restano conservati. Controlla configurazioni prima di riabilitare qualsiasi automatismo e registra nuovamente le passkey del cancello.

Prima del restore fermare anche il servizio telegram; la procedura revoca i collegamenti e disabilita l’integrazione. Restano da riabilitare consapevolmente ricorrenze, rivelazioni e notifiche. La prova del blocco 11 ha verificato il bundle cifrato con ledger conservato e autorizzazioni Telegram revocate; le prove sul server reale restano nella checklist di rilascio.


## Recupero dal web

Per migrazione iniziale e singoli gruppi usa il formato `.sgp`: [guida](backup-portabile.md). La procedura `.sgb` sopra rimane disponibile per il recupero server.
