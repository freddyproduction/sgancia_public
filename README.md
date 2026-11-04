# Sgancia

**Le spese si dividono. I bei momenti si moltiplicano.**

Spese condivise, conti chiari e uno spazio sul tuo server. Gratuito, open source e self-hosted, con FastAPI, PostgreSQL e React. Licenza [AGPL-3.0-only](LICENSE).

> **0.2.0-dev · sviluppo attivo.** Funzioni consegnate e testate localmente; qualificazione su server e dispositivi reali ancora aperta. PWA/offline completa e OCR non sono ancora disponibili. [Funzionalità e roadmap](ROADMAP.md).

## Cosa puoi fare

Gruppi e partecipanti, spese con più voci e pagatori, pubblici riservati, valute e conversioni, saldi Smart e rimborsi confermati dal ricevente. Storico, cestino, allegati, modelli, ricorrenze, statistiche, budget, import/export e PDF. Account con MFA/passkey, notifiche, bot Telegram e pannello globale con backup cifrati e audit.

Telegram, link ospiti e backup automatici richiedono attivazione/configurazione; SMTP e notifiche esterne richiedono i propri parametri. La [roadmap](ROADMAP.md) distingue ciò che è disponibile da ciò che va abilitato e da ciò che deve ancora arrivare.

## Avvio con Docker Compose

Il runtime completo è in Docker: API/frontend, database e servizi automatici, incluso Telegram in attesa quando disabilitato. Sul server non servono Python o Node installati separatamente.

**Prima dell’avvio devi compilare `.env`: i modelli lasciano le tre credenziali vuote apposta. Copiare il file e avviare subito Compose produce gli errori “POSTGRES_PASSWORD is missing” e “SGANCIA_ENCRYPTION_KEY is missing”.**

1. Nella cartella clonata, prepara il modello server senza sovrascrivere un `.env` esistente:

   ```sh
   test -e .env || cp .env.server.example .env
   ```

2. Genera i tre valori **sul nuovo server**, senza installare Python. Esegui ogni comando qui sotto una volta e conserva separatamente i risultati:

   ```sh
   # Risultato da inserire in POSTGRES_PASSWORD
   docker run --rm python:3.13-slim python -c 'import secrets; print(secrets.token_hex(32))'
   # Risultato da inserire in SGANCIA_ENCRYPTION_KEY
   docker run --rm python:3.13-slim python -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   # Altro risultato, distinto, da inserire in SGANCIA_BACKUP_KEY
   docker run --rm python:3.13-slim python -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   ```

3. Apri `nano .env`, incolla i tre valori nelle rispettive righe e compila dominio/IP LAN, origini, bind e proxy fidati secondo la [guida d’installazione](docs/installazione.md). Non incollare credenziali in chat, issue o Git. In nano salva con Ctrl+O, Invio, poi esci con Ctrl+X.
4. Solo dopo aver salvato la configurazione, controlla e avvia:

   ```sh
   chmod 600 .env
   docker compose config --quiet &&
   docker compose build migrate &&
   docker compose up -d &&
   docker compose exec api python -m app.cli init
   ```

   `config --quiet` verifica la configurazione senza stampare i segreti; `&&` ferma la sequenza al primo errore. Il bootstrap interattivo crea il primo superadmin e la chiave d’accesso al sito, distinta dalle tre credenziali tecniche sopra.

**Questa procedura genera chiavi per una nuova installazione. Se il database esiste già, conserva password e chiavi originali: non rigenerarle per aggiornare o correggere un errore.** Per un aggiornamento usa [la procedura dedicata](docs/aggiornamenti.md). Per prove solo locali segui la sezione localhost della guida.

Porta predefinita **8088**, bind predefinito loopback; il database non espone porte. L’inizializzazione interattiva crea il primo superadmin: non ci sono credenziali universali. Non copiare chiavi, account, database o dati di sviluppo su una nuova installazione.

Sono supportati dominio HTTPS, localhost, 127.0.0.1 e IP LAN HTTP dichiarato esplicitamente. L’esposizione tramite Nginx/Cloudflare Tunnel è a cura del gestore. Segui [installazione](docs/installazione.md), [amministrazione](docs/amministrazione.md) e [checklist rilascio](docs/rilascio.md).

## Guide

- **[Guida utente](docs/guida-utente.md)**, disponibile anche nell’app da Guida e informazioni e prima del login su `/help`.
- [Telegram](docs/telegram.md), [account e sicurezza](docs/sicurezza-account.md), [metodi di pagamento](docs/metodi-pagamento.md), [accesso ai gruppi](docs/accesso-gruppi.md), [inviti globali e approvazioni](docs/inviti-globali.md).
- [Allegati](docs/allegati.md), [import/export](docs/importazione-esportazione.md), [notifiche](docs/notifiche.md), [modelli e ricorrenze](docs/modelli-ricorrenze-anticipi.md).
- [Backup/ripristino](docs/backup-ripristino.md), [aggiornamenti](docs/aggiornamenti.md), [troubleshooting](docs/troubleshooting.md), [operatività](docs/operativita.md).
- [API](docs/api.md), [database](docs/schema-database.md), [architettura e permessi](docs/architettura-sicurezza.md), [sviluppo](docs/sviluppo.md), [Git e pubblicazione](docs/git.md).
- [Changelog](CHANGELOG.md), [contributi](CONTRIBUTING.md), [sicurezza](SECURITY.md), [contatti e donazioni](docs/contatti.md).

## Una firma dietro ai conti

**Ideato e sviluppato da PjChaosEOW**, con vibecoding e ChatGPT: idee, iterazioni e cura dei dettagli, per condividere le spese con più leggerezza.

Email, repository pubblico e Buy Me a Coffee sono configurabili e rimangono nascosti finché non vengono inseriti recapiti reali. Le donazioni sono interamente volontarie, senza acquisto di funzionalità, obblighi, priorità delle richieste, legami con lo sviluppo del codice o promesse su tempi e risultati.
