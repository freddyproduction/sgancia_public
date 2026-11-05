# Backup portabile, migrazione e ripristino

| Archivio | Contenuto | Creazione | Ripristino |
|---|---|---|---|
| `.sgp` installazione | Account, ruoli, amicizie, preferenze, gruppi, storico e allegati | Impostazioni → Amministrazione → Migrazione e backup portabili; solo superadmin con password/MFA e identità recente | Configurazione iniziale di una destinazione vuota, senza creare un altro admin |
| `.sgp` gruppo | Intero gruppo, comprese spese riservate, revisioni, ledger, rimborsi, allegati, categorie, controversie, budget/report, modelli e storico | Admin/proprietario → Impostazioni gruppo → Gestione avanzata | Panoramica → Ripristina gruppo oppure Gestione avanzata; nuova copia congelata |
| `.sgb` server | Dump PostgreSQL compresso e file immutabili, cifrati con SGANCIA_BACKUP_KEY | Backup automatici del pannello o script conservativo già presente | Procedura server in [backup e ripristino](backup-ripristino.md), non nel modulo `.sgp` |

## Creazione e protezione

Scegli nome del file e password di almeno 12 caratteri. `.sgp` è JSON strutturato compresso, protetto con AES-256-GCM, chiave derivata con scrypt e sale casuale. Non contiene SQL eseguibile. La password non è recuperabile: conserva file e password separatamente. Il browser gestisce la destinazione del download; puoi abilitarne la scelta nelle sue impostazioni.

**Il backup contiene anche i dati riservati. Chi possiede file e password può decifrarli fuori dall’app.** Dopo il ripristino, l’app conserva i destinatari delle spese e non le rende pubbliche. Non è cifratura end-to-end contro chi possiede l’archivio.

Limite web: 128 MB predefiniti, fino a 512 MB configurabili, applicato anche ai dati serializzati prima della compressione e alle immagini in base64. Per archivi grandi usa `.sgb` e il recupero server. Password errata, file alterato/troncato, riferimenti esterni, contabilità non riconciliata o formato incompatibile annullano l’importazione. I file immutabili eventualmente già verificati restano inutilizzati se la transazione viene annullata; nessun gruppo parziale viene pubblicato.

Il nuovo formato è legato allo schema `fb24a762bd25`: usa una versione compatibile per recuperare e poi aggiorna. Non modificare il numero di schema nel file. Il codice si installa dal repository; `.env`, password PostgreSQL, chiavi tecniche, dominio, IP e proxy si configurano separatamente. Nessun `.env` del Mac va copiato in produzione.

## Migrazione senza admin provvisorio

1. Dalla sorgente scarica il backup completo `.sgp` e conserva la password.
2. Installa sulla destinazione una versione compatibile, prepara `.env` con **nuove chiavi/password**, dominio/IP della destinazione e avvia Compose. Non eseguire `app.cli init`.
3. Apri il frontend: compare **Configura l’installazione → Ripristina o migra**.
4. Inserisci `SGANCIA_ENCRYPTION_KEY` del **nuovo** `.env`, il backup e la sua password. La chiave del nuovo server dimostra che ne sei il gestore; non decifra il file. Non inviarla in chat o issue.
5. Conferma e accedi con la chiave globale e l’account originali. Non si crea un nuovo admin: identità e superadmin restano conservati. TOTP e metodi di pagamento vengono ricifrati con la nuova chiave applicativa.
6. Controlla dati e allegati, quindi verifica SMTP, Telegram, notifiche, ricorrenze, rivelazioni e pianificazione backup prima di riattivarli.

Le sessioni e i token/link precedenti non vengono importati. Le amicizie restano ma i loro link vanno ricreati; lo stesso vale per i codici dei gruppi. Collegamenti Telegram e code esterne non vengono ripristinati. SMTP, notifiche e automatismi sono disabilitati. Le passkey personali restano vincolate al dominio originale: su un dominio nuovo usa password/MFA e registra nuove passkey.

Una destinazione già configurata rifiuta il ripristino completo. Nessuna fusione di installazioni o sovrascrittura dal web. La scheda **Nuova installazione**, con la stessa autorizzazione tecnica, crea invece il primo superadmin quando parti da zero. Configura reverse proxy e relativi limiti di upload/timeout per la dimensione scelta; eventuali limiti Cloudflare restano esterni al prodotto.

## Copia o migrazione del gruppo

Il backup include **tutte** le spese, anche quelle riservate escluse alla vista dell’admin, come richiesto dal titolare. Il ripristino crea un gruppo congelato con nuovi ID e file indipendenti, senza modificare l’originale o duplicare pagamenti nel suo ledger.

Chi ripristina prende il posto del partecipante che ha esportato e diventa proprietario della copia. Gli altri partecipanti sono virtuali; i destinatari privati sono rimappati senza aggiungervi il proprietario. Dopo il controllo dei dati puoi riaprire il gruppo e collegare le persone con i normali inviti/claim, senza abbinamenti automatici per nome o email.

Gli altri autori restano riferimenti storici interni non autenticabili, esclusi dalla gestione account. Budget/report personali e titolarità dei modelli altrui sono conservati, **senza trasferirli automaticamente all’admin o a un account diverso**. Per conservare integralmente le identità personali usa la migrazione completa dell’installazione. Modelli e rivelazioni sono sospesi, deleghe revocate; sessioni, inviti, amicizie e impostazioni globali non fanno parte del backup di gruppo.

## Parametri e destinazioni

Admin globale con permesso Backup o superadmin: abilitazione backup/ripristino gruppi, limite web e prefisso suggerito. Solo superadmin: estrazione intera installazione. Admin gruppo: nome/password del proprio archivio entro tali limiti.

Il servizio automatico `.sgb` conserva pianificazione, retention e prove isolate già disponibili; puoi scegliere prefisso e sottocartella dentro `backups/automatic`. Sono ammessi lettere, numeri, trattino e underscore; retention anche sui vecchi prefissi/sottocartelle. Per altri dischi/NAS cambia il volume del servizio backup in Compose. Il pannello non concede percorsi filesystem arbitrari o accesso al socket Docker. I download `.sgp` seguono invece le impostazioni del browser.
