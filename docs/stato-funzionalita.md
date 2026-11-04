# Stato delle funzionalità — 3 novembre 2026

Il nucleo è eseguibile e verificato; il perimetro del primo prompt resta interamente approvato e viene consegnato progressivamente. Versione ancora di sviluppo. Checklist operativa: [TODO-SVILUPPO](../TODO-SVILUPPO.md).

| Area | Stato verificato | Ancora da completare |
|---|---|---|
| Runtime | Compose PostgreSQL, API/React, migrazioni, storage, worker mail e ricorrenze | Bot e servizi opzionali futuri |
| Login e account | Gate, Argon2id, sessioni, CSRF/origini, tema per account, cambio/recupero password, verifica email | Prova consegna con SMTP reale configurato dal titolare |
| MFA/passkey | TOTP/recovery e passkey con firme simulate; rimozione personale e recupero globale selettivo, superadmin escluso | Prove passkey reali Mac/iPhone |
| Admin | Modalità registrazione, inviti, approvazione/sospensione, modifica utenti, rotazione gate | Politiche/parametri, audit e monitoraggio completi, backup/aggiornamenti da pannello |
| Gruppi | Ruoli/virtuali, inviti/claim, stati, dettagli, proprietà, uscita/riattivazione, fusioni reversibili e deleghe granulari | Verifiche avanzate del backlog |
| Spese/calcoli | Centesimi/Decimal, cinque modalità, composte, stelle pagatori, categorie/tag, calcolatrice con formule facoltative, revisioni, duplicazione, modelli, ricorrenze e anticipi dedicati | Strumenti dei blocchi successivi |
| Valute | 20 valute a due decimali, cambio automatico/manuale, controvalore immediato, cambio valuta principale con storico | Altre valute/unità minime e i18n completa |
| Saldi Smart | Default attivo, disattivabile per gruppo; riduzione trasferimenti oppure debiti diretti per voce/spesa, con pubblici separati | Simulazioni e casi avanzati del backlog |
| Panoramica | Crediti/debiti da tutti i gruppi, popup per persona, valute distinte, account collegati riconosciuti; Saldato atomico nei gruppi originari | Nessuna fusione automatica di virtuali omonimi: resta il futuro percorso di associazione/fusione |
| Rimborsi | Parziali, conferma ricevente, Saldato diretto/globale, annullamento/ripristino, cronologia, ricevute, contestazioni motivate e deleghe | Automazioni/promemoria futuri |
| Allegati | JPG/PNG/WebP/PDF validati localmente, anteprime immagini, download protetti, file privati persistenti, quote e cestino/ripristino; spese e rimborsi | Nessun OCR; cancellazione fisica/retention amministrativa nel blocco 14 |
| Privacy/ospiti | Ambiti rigorosi, esclusi senza effetti visibili, rivelazione manuale/programmata, riconciliazione esplicita degli incassi, link limitati/revocabili; originali e allegati privati conservati | Controlli sulle future integrazioni |
| Web/mobile | Italiano, menu completo mobile, temi per account, form responsive e popup centrati/scorrevoli; immagini/PDF e ricevute provati in browser mobile | Accessibilità sistematica, prove smartphone reali, schermate future |
| PWA/offline | Manifest presente | Service worker, installazione completa, cache opt-in, coda/sync e conflitti |
| Telegram | Implementato, servizio opzionale spento di default | Prova bot reale e webhook HTTPS; dettagli in telegram.md |
| OCR | Pianificato, non implementato | Motore e integrazione blocco 12 |
| Strumenti avanzati | Ricerca/filtri, budget/grafici, simulazioni, riepiloghi finali e import/export CSV/JSON/PDF | PWA e funzioni successive |
| Backup | DB+file privati con manifest/digest e cifratura autenticata, compatibilità legacy, ripristino reale completo QA riuscito | Pianificazione, retention, pulizia e ripristini periodici operativi |
| Accessi/deploy | Dominio HTTPS e alias locali/LAN configurabili; accesso locale e LAN verificato sul Mac secondo .env dell’utente | Server Linux e Nginx/Tunnel reali, firewall e verifica infrastruttura |
| Documentazione/CI | Brain, checklist, guide tecniche e workflow CI presenti | Completamento progressivo, pipeline remota attestata e rilascio stabile |

**Ultima verifica completa:** 110 backend PostgreSQL in Docker + 9 frontend, build TypeScript/Vite e migrazioni upgrade/check/downgrade riusciti. Test allegati includono privacy, ospiti, file invalidi/corrotti, limiti e commit ambiguo. Test dashboard includono identità, valute, Smart, idempotenza e rollback su più gruppi. Nessuna revisione di sicurezza indipendente dichiarata.

**Prove operative:** backup e ripristino con gli script reali su progetto QA isolato, dopo eliminazione di schema e file sintetici: metadati, hash e saldi recuperati. Browser: immagine/PDF, anteprima/download, cestino/ripristino, ricevuta, Smart on/off, dashboard e Saldato generale su sola persona sintetica; debito di prova ripristinato. Nessuna spesa o rimborso reale modificato durante QA. Backup completo DB+allegati della copia in uso riuscito dopo l’upgrade.

**Blocco 01 concluso.** Guida integrata e contatti sono stati successivamente consegnati nel blocco 16. Prossimo blocco della checklist: 02, cronologia e contestazioni complete.


## Cestino gruppi e archivio — 3 novembre 2026

Eliminazione reversibile del gruppo dalle impostazioni, riservata al proprietario con conferma del nome e controllo versione. Gruppo nascosto a tutti, escluso dai saldi della panoramica e non accessibile tramite endpoint ordinari. Dati, spese, rimborsi e file conservati. Cestino dei gruppi nella panoramica, ripristino riservato al proprietario che conserva lo stato precedente. Link ospite, inviti e claim revocati all’eliminazione non si riattivano al ripristino.

Archiviati nascosti di default nell’elenco laterale e nelle schede della panoramica; icona archivio accanto a “I tuoi gruppi” mostra/nasconde, anche su mobile. Il filtro non cancella i saldi dei gruppi archiviati dalla dashboard generale.


## Blocchi 02 e 03 conclusi — 3 novembre 2026

Cronologia spese con confronto revisioni, autore/data e valuta/tasso storico. Contestazioni delle quote motivate, esiti resolved/rejected/withdrawn tracciati, senza rettifiche monetarie implicite. Eventi rimborsi e conversioni consultabili; contestazione e risoluzione ricevente con motivazione, undo conservato. Nuovi eventi ordinati anche all’interno dello stesso secondo. Rivelazione non espone vecchi snapshot, contestazioni o allegati riservati a nuovi lettori; protezione presente anche sul vecchio endpoint /versions e sui download ospiti.

Gestione avanzata: proprietà con proposta di 24h e accettazione del destinatario, controllo versione e identità recente; uscita/rimozione conserva ledger e persona inattiva senza account, revoca accesso/inviti/claim/deleghe, con scelta esplicita sui saldi aperti e anteprima verificata. I gestori non ricevono indizi sugli eventuali saldi riservati di chi rimuovono. Riattivazione torna virtuale, senza riassociare silenziosamente l’account. Fusione di sorgente virtuale verso persona attiva con anteprima saldi, nuovi snapshot immutabili, eventi rimborso, revoca codici e ripristino finché nessuna modifica successiva. Blocco conservativo per due account, pubblici storici differenti o rimborsi fra i duplicati. Deleghe granulari pagamento/attestazione di 1–90 giorni, revocabili e prive di nuovi accessi riservati; pagamenti e Saldato autorizzati anche al delegato, con account agente negli eventi. Claim email-bound esposto nella gestione membri e nella panoramica.

Migrazione d790e321ab04: participants.active/merged_into; settlement_events.reason/ordinal; nuove expense_disputes, group_operations e virtual_delegations. Lock del gruppo comune a scritture, claim e inviti per serializzare revoche e associazioni. Backup cifrato DB+file pre-upgrade creato, migrazione applicata. 130 test backend PostgreSQL e 9 frontend passati; build e upgrade/check/downgrade riusciti. Prova browser mobile: spesa sintetica e modifica note, confronto versioni, contestazione/ritiro; fusione/ripristino, uscita/riattivazione di soli virtuali sintetici. Gruppo QA archiviato dopo la verifica, saldo netto nullo. Nessun gruppo reale modificato. Screenshot fusione-sintetica.png limitato al popup di persone sintetiche, senza account o dati personali.

Documentazione dettagliata docs/cronologia-e-membri.md, TODO aggiornata. Prossimo blocco 04 non avviato. Le operazioni strutturali richiedono gruppo attivo; visualizzatori consultano senza modificare. L’ordine infrasecondo degli eventi legacy non era registrato: conservato l’orario originale, precisione nuova solo per nuovi eventi.


## Blocco 04 — software consegnato, verifiche esterne aperte — 3 novembre 2026

Cambio password, recupero email con token monouso/30 min e percorso locale interattivo senza cloud; recupero conserva MFA salvo procedura locale esplicita di revoca di tutti i fattori. Verifica email 24h, reinvio limitato e token legati a email/finalità/versione account; cambio email azzera verifica e revoca altre sessioni. Account preesistenti continuano a funzionare: verifica richiesta per condivisione nuovi metodi di pagamento e recupero via posta, non blocco retroattivo delle spese.

MFA TOTP compatibile con Google Authenticator: rotazione con vecchio fattore valido fino alla conferma del nuovo, disattivazione e rinnovo recovery con password+fattore; altre sessioni invalidate. auth_version su utenti/sessioni contrasta emissioni concorrenti obsolete; revoche invalidano anche challenge e token temporanei. Revoca passkey conserva solo la sessione corrente. Nuovi test di firma, revoca e origine principale; nessuna passkey reale creata/rimossa dall’agente. L’utente ha indicato Mac e iPhone: prova hardware ancora DA VERIFICARE, iPhone richiede dominio HTTPS principale e certificato valido.

Metodi di pagamento account senza limite funzionale numerico, istruzioni cifrate, immagini private PNG/JPEG/WebP massimo 2 MB/16 MP, ricodifica 512 px e quota immagini account 25 MiB. Privati per default; condivisione esplicita richiede email verificata, visibile soltanto al debitore con trasferimento autorizzato corrente verso l’account titolare. Download immagini ricontrolla i permessi; no ospiti o bypass admin gruppo. Nessun pagamento eseguito o credenziale bancaria conservata.

Su richiesta esplicita successiva, SMTP gestibile da Impostazioni dell’installazione dell’admin globale: host, porta, STARTTLS/TLS diretto, mittente, utente/password; credenziali cifrate nel DB, password mai restituita (neppure errori validazione), opzioni conserva/elimina, identità recente e audit. Prova invio solo verso l’admin corrente, conteggi coda/fallimenti. Configurazione web prevale sui valori iniziali env. Servizio mail nello stesso Compose, senza porte pubblicate, rilegge configurazione senza riavvio, coda cifrata con scadenza/retry e scarto token superati. Nessun parametro SMTP reale inserito né email reale inviata durante lo sviluppo; consegna e verifica effettiva ancora DA VERIFICARE dall’utente.

Gate opzionale realizzato nel blocco 04 anticipando 14: abilitato di default, solo admin globale con identità recente e conferma, revoca sessioni/concessioni per entrambi i cambi. Non disabilita login personale/MFA/CSRF/ruoli. Installazione reale lasciata con gate attivo, chiavi e credenziali invariate. Ruoli globali e di gruppo separati nella UI e nelle prove permessi.

Migrazione e82d4195ca06 applicata. 151 backend PostgreSQL e 9 frontend passati, TypeScript/Vite e upgrade/check/downgrade riusciti. Backup completo pre-upgrade e ripristino reale solo nel progetto isolato sgancia-account-qa: metodi, immagine e SMTP recuperati; sessioni, challenge, token email/recupero e coda eliminati dal restore per non resuscitare accessi. QA rimosso. Prova browser mobile in sola lettura delle nuove impostazioni e SMTP vuoto; screenshot impostazioni-smtp.png ritagliato sui soli campi vuoti/segnaposto, senza account o dati reali. Nessun gruppo/saldo o credenziale reale modificato.

TODO blocco 04 mantiene aperte prova hardware Mac/iPhone e ricezione SMTP reale. Documenti docs/sicurezza-account.md e docs/metodi-pagamento.md; restore ora richiede stop api e mail. Non dichiarare concluse le verifiche esterne. Prossimo sviluppo disponibile 05 se richiesto.


## Ruoli globali operativi — 3 novembre 2026

Aggiunti Nomina admin globale/Rimuovi admin globale in Impostazioni → Gestione utenti e ruoli globali. Solo admin globale attivo, identità recente, password del richiedente e MFA/recupero quando attivo, conferma esplicita UI. Solo account attivi promuovibili; controllo stato atteso contro sovrascritture obsolete. Cambio ruolo revoca sessioni, challenge e token del destinatario, senza cambiare ruoli o appartenenze ai gruppi e senza ampliare accessi riservati. Autorimozione ammessa soltanto con altro admin attivo e forza logout. Impossibile togliere l’ultimo admin globale attivo anche con richieste concorrenti; amministratori sospesi/in attesa non valgono come riserva.

Lock installazione e utenti ordinati con rilettura del ruolo/sessione correnti, condiviso anche da sospensione e modifica account per impedire gare con promozione/revoca. Audit di assegnazione/revoca. Etichette Ruolo nel gruppo/Amministratore del gruppo esplicite in modifica partecipante, aggiunta e inviti. Nessuna migrazione necessaria: usa User.admin e Participant.role già distinti.

157 backend PostgreSQL + 9 frontend passati, build e ciclo migrazioni riusciti. Test dedicati promozione/revoca/sessioni, nessuna espansione dei gruppi, separazione ruolo gruppo, password/MFA/CSRF/identità recente, ultimo admin e due gare concorrenti. Backup completo pre-aggiornamento riuscito, API/DB healthy e mail avviato. Nessun ruolo reale modificato. La sessione browser aperta risultava disconnessa: verifica manuale della pagina autenticata da fare al prossimo accesso del titolare; nessuna credenziale reale letta o inserita per forzarla. Documentazione amministrazione aggiornata. Verifiche esterne del blocco 04 (SMTP reale/passkey Mac-iPhone) restano aperte.


## Superadmin fondatore permanente — 3 novembre 2026

Richiesta esplicita dell’utente: il primo account dell’installazione diventa superadmin permanente. Implementato tramite instance.superadmin_id immutabile e FK all’ID, senza nomi/email hardcoded. L’istanza attuale è stata verificata senza stampare dati personali: l’admin iniziale è identificabile e coincide col primo attore registrato. Migrazione f913a762bd08 applicata: fondatore assegnato, admin attivo e identità originale confermati. Nessun account aggiuntivo creato o promosso nell’istanza reale.

API/interfaccia impediscono declassamento e sospensione; altri global admin non possono modificare l’account del fondatore. Modifiche personali legittime (nome, email/password/MFA con le relative verifiche) conservano l’identità protetta. Trigger PostgreSQL e FK bloccano anche cancellazione/modifica ID, revoca admin, cambio stato, azzeramento/sostituzione del fondatore e cancellazione riga installazione. UI indica Superadmin fondatore protetto e non mostra Rimuovi admin globale per lui. Admin globali ordinari restano gestibili; nessun bypass delle privacy dei gruppi. Recupero locale mantiene l’identità, non crea un altro superadmin.

Nuovo bootstrap assegna primo User nello stesso commit; seconda inizializzazione rifiutata. Legacy: assegnazione automatica solo se non ambigua, altrimenti identificazione locale esplicita SGANCIA_LEGACY_SUPERADMIN_ID. Downgrade su installazione inizializzata bloccato. Backup completo pre-migrazione creato. 161 backend PostgreSQL + 9 frontend, build e ciclo migrazioni riusciti. QA isolato senza porte: migrazione legacy, vincoli SQL, backup/ripristino del fondatore e nuovo bootstrap protetto riusciti; ambiente QA rimosso. API/DB healthy, mail avviato. Nessuna password o chiave reale modificata. Verifiche esterne precedenti SMTP/passkey ancora aperte.


## Rimozione e recupero MFA/passkey — 3 novembre 2026

Richiesta utente chiarita: rimozione personale e recupero da admin globale sugli altri account, escluso il superadmin. Comandi personali MFA resi espliciti con effetti chiari; passkey in pannello autonomo Passkey: aggiungi o rimuovi, con conferma per la revoca di ogni chiave, fino a rimuoverle tutte. Nessuna disattivazione automatica incrociata: togliere MFA conserva passkey, togliere passkey conserva MFA. Codici di recupero invalidati non più mostrati dopo disattivazione.

Nuovo recupero amministrativo in Gestione utenti e ruoli globali → Recupera MFA/passkey: selezione separata remove_mfa/remove_passkeys, conferma verifica titolare, identità recente e password/MFA dell’operatore. Target superadmin e target uguale all’operatore esclusi da API/UI. Revoca sessioni, challenge e token temporanei del destinatario, senza cambiarne password/email/stato/ruoli. Audit separato per i fattori selezionati, limite cinque richieste ogni cinque minuti. Il superadmin usa i percorsi personali o il recupero locale del server in caso di perdita totale, senza scorciatoia web degli altri admin.

167 test backend PostgreSQL e 9 frontend passati, build e ciclo migrazioni riusciti. Nuovi test: entrambi i fattori e selezione singola, sessioni/challenge/token invalidati, factor proof/recent/CSRF/conferma, admin di gruppo escluso, superadmin escluso e propri reset amministrativi vietati. Nessuna nuova migrazione: usa lo schema f913a762bd08. Backup pre-deploy e aggiornamento Compose eseguiti. Nessuna credenziale, MFA o passkey reale rimossa dall’agente. Verifiche hardware/SMTP reali già aperte restano aperte.

Blocco 05: vedi [modelli, ricorrenze e anticipi](modelli-ricorrenze-anticipi.md). Il worker crea solo ricorrenze autorizzate; nessun piano reale è stato creato dall’agente. Il ripristino sospende le ricorrenze per revisione manuale.

## Blocco 06

Ricerca/filtri paginati, statistiche con grafici categoria/mese e personali multigruppo per valuta, budget privati/pubblici con soglie, simulazioni non persistenti e chiusura guidata con report personali implementati. 193 test backend PostgreSQL e 10 frontend passati; build e ciclo upgrade/check/downgrade riusciti. Browser QA con soli dati sintetici: ricerca, budget/soglia, simulazione, congelamento, riepilogo privato e chiusura con saldo aperto verificati. Backup/ripristino QA recupera budget e riepiloghi, conserva gruppo archiviato e credito aperto; nessun pagamento creato dalla simulazione. Uso e limiti: [ricerca e chiusura](ricerca-statistiche-chiusura.md). Non sono notifiche di budget, budget ricorrenti o esportazioni del blocco 07.

## Blocco 07

Import/export autorizzati implementati. 212 test backend PostgreSQL e 11 frontend passati; build, upgrade/check/downgrade e PDF multipagina renderizzato/ispezionato riusciti. UI QA: file CSV caricato, associazioni esplicite, quote controllate, importazione e riconoscimento al secondo tentativo; download CSV/JSON/PDF confrontati (2 spese sintetiche, totale 110 EUR). Backup/ripristino QA conserva provenienza e conferme applicate, annulla anteprime pendenti, riconcilia pagato/quote e impedisce la reimportazione della stessa origine. [Formati, limiti e uso](importazione-esportazione.md). Non sono un ripristino di account/pagamenti/allegati né importatori per formati di altri prodotti.

Blocco 09: centro notifiche con lettura e contatori autorizzati, preferenze account/gruppo, promemoria per debiti con soglie e riepiloghi giornalieri/settimanali. Email facoltative su indirizzi verificati, coda cifrata, deduplicazione, retry e controllo permessi prima dell’invio. Invii reali subordinati a SMTP configurato; Telegram aggiunto nel blocco 11; push ancora successivo. Dettagli in `notifiche.md`.

Blocco 13A: revisione accessibilità UI consegnata e verifiche automatiche/Chrome Mac superate; prove VoiceOver e Safari/iPhone reale ancora aperte. Vedi `accessibilita.md`.

Blocco 09A consegnato: notifiche con fusi/durata/filtri e pianificazione personalizzabili, soglia in importi e uscita gruppi più chiara. Passkey globali separate, revocabili e verificate con autenticatore virtuale; modulo chiave compatibile con gestori password. Prove hardware/autofill reale aperte.

Blocchi 14/18 consegnati: politiche/monitoraggio/audit amministrativi, backup schedulati con probe isolato e retention, aggiornamento guidato, inviti/associazioni con anteprima/revoca e separazione ospiti. Telegram aggiunto successivamente nel blocco 11. Prove server reale nei blocchi successivi.

Blocchi 15/16: versione 0.2.0-dev; guida integrata/Markdown sincronizzata, firma PjChaosEOW, idee e recapiti configurabili, roadmap pubblica, changelog e cataloghi API/DB. Qualifica locale completa e copia pubblicabile separata; server Linux reale, CI remota, dispositivi e revisione finale sicurezza/licenze restano aperti. Non dichiarare release stabile.

Aggiornamento 4 novembre — autorità globale: la precedente permanenza del solo fondatore è superata dalla richiesta esplicita di più superadmin. Solo un altro superadmin revoca il ruolo; l’ultimo è protetto e nessun account viene eliminato. Permessi per-admin e ruoli negli inviti/approvazioni disponibili: docs/ruoli-globali.md.
