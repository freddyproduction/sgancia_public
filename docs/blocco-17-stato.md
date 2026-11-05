# Blocco 17 — avanzamento

La TODO principale contiene modifiche dell’utente: questa checklist di consegna le conserva senza sovrascriverle.

- [x] Backup intera installazione: formato server `.sgb` già presente, archivio portabile `.sgp` compresso/cifrato aggiunto.
- [x] Migrazione/ripristino da web prima del bootstrap, senza un nuovo admin; account e ruoli conservati, segreti ricifrati per il nuovo server.
- [x] Backup completo del singolo gruppo da admin/proprietario, incluse spese riservate, quote, rimborsi, allegati, revisioni, modelli e storico.
- [x] Ripristino gruppo in copia congelata indipendente, con destinatari privati conservati e altri partecipanti virtuali; nessuna sovrascrittura.
- [x] Parametri piattaforma: abilitazione gruppi, limite web e prefisso; nome/password download; prefisso/sottocartella archivi automatici.
- [x] Pianificazione, retention e prove isolate del backup server già presenti e conservate.
- [x] Validazione file, schema, integrità, riferimenti interni e riconciliazione ledger; revoca token/link e sospensione automatismi nel recupero.
- [x] Guide utente, installazione, amministrazione, API/schema e roadmap aggiornate.

[Guida completa](backup-portabile.md). Limite web predefinito 128 MB, massimo 512 MB; grandi archivi e vecchi `.sgb` usano il recupero server. Download nelle destinazioni del browser; dischi/NAS del server configurati tramite i volumi Compose, senza percorsi arbitrari dal web. Dati personali degli altri autori sono conservati per lo storico senza trasferirne automaticamente la titolarità: per conservarne identità e impostazioni operative usare la migrazione dell’installazione.

## Amici — aggiunta alla consegna

- [x] Lista e filtro per nome, ricerca di nuovi account con email esatta.
- [x] Richieste esplicite, accettazione, rifiuto, annullamento e rimozione.
- [x] Link privato personale Facciamo amicizia, a scadenza, revocabile e rigenerabile.
- [x] Ricerca degli amici confermati e aggiunta ai gruppi da admin del gruppo.
- [x] Icona dedicata, avatar protetti e menu desktop/mobile.

[Guida Amici](amici.md).
