# Revisione applicativa mirata — 4 novembre 2026

Questa è una verifica interna del codice e delle prove automatiche, non una certificazione, una revisione indipendente o la qualifica dell’host reale.

| Confine | Evidenza locale | Limite |
|---|---|---|
| Account e privilegi | Suite completa: sessioni/revoche, MFA/passkey, ruoli globali, fondatore, verifiche recenti | Hardware e SMTP reale aperti |
| Gruppi e pubblici | Suite API/storico/allegati/report/notifiche: esclusi, visualizzatori, ambiti e risorse invisibili | Pentest indipendente aperto |
| Ledger e rimborsi | Test esatti/arrotondamenti, concorrenza, versioni e idempotenza; flusso browser spesa e saldo | Nessuna attestazione bancaria |
| Telegram | ID verificato, codici/pulsanti, replay, revoca, privati, retry e scopi testati con API simulate | Provider e webhook reali aperti |
| Nuova guida/contatti | Endpoint pubblico statico senza segreti, link validati/assenti se vuoti; nessun invio automatico; browser mobile/chiaro/scuro/accessibilità | Nessun recapito reale configurato |
| Cache/offline | Header no-store; assenza di service worker applicativo dichiarato | Blocco 10 ancora aperto, revisione cache da rifare quando introdotta |
| Riavvio/rete/carico | QA separata: 30 letture finance concorrenti senza errori, offline/online browser, restart API/worker e conti persistenti | Smoke locale, non capacity planning né guasto host |
| Recupero | Bundle cifrato ripristinato su QA separata; ledger e identità conservati, integrazione revocata | Host remoto/backup esterno reale aperti |
| Dipendenze | npm audit: zero note; pip-audit: 43 dipendenze, zero note; inventario licenze | Esito puntuale, transitive/binary/legal review da completare |
| Pubblicazione | Sorgenti selezionati, controllo segreti e copia locale Git separata | Remoti, identità pubblica e CI remota non forniti |

Le nuove informazioni progetto non accettano dati dell’utente nel server: i recapiti vengono dal solo file pubblico di configurazione. Le proposte rimangono nello stato locale della pagina; copia e mailto sono azioni esplicite e non creano una coda email. Non esistono link donazioni se il valore reale è vuoto. Il disclaimer è stato approvato dal titolare.

Le prove sul server reale sono elencate in rilascio.md. Non spuntare il blocco 15 come interamente completato prima di averle eseguite e registrate.
