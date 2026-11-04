# Qualifica e prima pubblicazione

Stato: **0.2.0-dev**, non release stabile. Il blocco 15 prepara e verifica ciò che è riproducibile localmente; non attesta prove su host o servizi non disponibili.

## Due repository distinti

1. La cartella master è il repository di sviluppo, con branch develop/feature/main, TODO e memoria del progetto. `.env`, DB, allegati, backup, dipendenze e strumenti locali sono esclusi. Il backup completo dell’installazione è un archivio cifrato separato: non è Git e non va inserito neppure in un repository privato.
2. La copia per pubblicazione contiene soltanto sorgenti versionati selezionati, documentazione pubblica, template, licenza e CI. Niente cronologia privata, brain, TODO interna, screenshots di QA o documenti delle prove locali. Si prepara dopo il commit verificato con `python3 scripts/prepare_public_repository.py`. La destinazione nuova è sotto `.local/publication` nella cartella master; lo script rifiuta sovrascritture. Non crea repository online e non esegue push. Prima del primo commit pubblico scegliere identità/email pubblica del titolare e controllare file e licenze.

Nessun remoto viene inventato. Servono due destinazioni reali del titolare: una privata di sviluppo e una pubblica. In ciascuna verificare accessi e contenuti prima di collegare il remoto. La pipeline è già presente; la sua esecuzione remota rimane aperta finché non viene pubblicata e attestata.

## Verifiche locali

- Suite completa backend su PostgreSQL, test frontend e build produzione.
- Upgrade/check/downgrade su database temporaneo vuoto; mai downgrade sui dati reali.
- Browser su istanza QA separata: desktop/mobile, guida, login, gruppi, spese, saldi e autorizzazioni.
- Concorrenza/idempotenza, errori provider simulati, restart e recupero con dati sintetici.
- Backup cifrato/ripristino e conservazione delle identità/conti; revoca sessioni e sospensione automatismi.
- Audit dipendenze e inventario licenze, controllo segreti, guida sincronizzata e documentazione generata dal codice.

Gli esiti sono documentati nella copia di sviluppo, senza riportare dati o chiavi. Gli audit automatici rilevano soltanto problemi conosciuti e non sostituiscono una revisione indipendente.

## Checklist sul server reale — da eseguire prima della release stabile

- [ ] Server Linux scelto, architettura supportata, spazio e permessi persistenti, Docker/Compose aggiornati.
- [ ] Clone della copia pubblica verificata, nuove chiavi/password, bootstrap superadmin e copie di recupero separate.
- [ ] Dominio HTTPS, localhost/127.0.0.1 e IP LAN HTTP effettivi; Host/protocollo inoltrati e soli proxy realmente fidati.
- [ ] Nginx, Cloudflare Tunnel e firewall del gestore: nessun accesso pubblico diretto a database/storage; header HTTPS e cookie verificati nel browser.
- [ ] Riavvio host, persistenza database/allegati, readiness e servizi automatici.
- [ ] Backup esterno cifrato e ripristino su ambiente separato usando le chiavi originali.
- [ ] Aggiornamento con backup e recupero manuale provato; nessun reset del DB per cambiare credenziali.
- [ ] Passkey Mac/iPhone sul dominio finale, consegna SMTP, Telegram e webhook reali.
- [ ] CI remota verde, revisione licenze e sicurezza, changelog e roadmap aggiornati.
- [ ] Tag stabile solo dopo queste prove e risoluzione dei blocchi aperti.

La firma PjChaosEOW è editoriale e visibile; non viene dichiarata una firma crittografica senza una chiave di firma del titolare.
