# Sgancia

**Le spese si dividono. I bei momenti si moltiplicano.**

Spese condivise, conti chiari e uno spazio sul tuo server. Gratuito, open source e self-hosted, con FastAPI, PostgreSQL e React. Licenza [AGPL-3.0-only](LICENSE).

> **0.2.0-dev · sviluppo attivo.** Funzioni consegnate e testate localmente; qualificazione su server e dispositivi reali ancora aperta. PWA/offline completa e OCR non sono ancora disponibili. [Funzionalità e roadmap](ROADMAP.md).

## Cosa puoi fare

Gruppi e partecipanti, spese con più voci e pagatori, pubblici riservati, valute e conversioni, saldi Smart e rimborsi confermati dal ricevente. Storico, cestino, allegati, modelli, ricorrenze, statistiche, budget, import/export e PDF. Account con MFA/passkey, notifiche, bot Telegram e pannello globale con backup cifrati e audit.

Telegram, link ospiti e backup automatici richiedono attivazione/configurazione; SMTP e notifiche esterne richiedono i propri parametri. La [roadmap](ROADMAP.md) distingue ciò che è disponibile da ciò che va abilitato e da ciò che deve ancora arrivare.

## Avvio con Docker Compose

Il runtime completo è in Docker: API/frontend, database e servizi automatici, incluso Telegram in attesa quando disabilitato. Sul server non servono Python o Node installati separatamente.

```sh
cp .env.example .env
# Generare nuove chiavi e configurare le origini secondo docs/installazione.md.
docker compose build migrate
docker compose up -d
docker compose exec api python -m app.cli init
```

Porta predefinita **8088**, bind predefinito loopback; il database non espone porte. L’inizializzazione interattiva crea il primo superadmin: non ci sono credenziali universali. Non copiare chiavi, account, database o dati di sviluppo su una nuova installazione.

Sono supportati dominio HTTPS, localhost, 127.0.0.1 e IP LAN HTTP dichiarato esplicitamente. L’esposizione tramite Nginx/Cloudflare Tunnel è a cura del gestore. Segui [installazione](docs/installazione.md), [amministrazione](docs/amministrazione.md) e [checklist rilascio](docs/rilascio.md).

## Guide

- **[Guida utente](docs/guida-utente.md)**, disponibile anche nell’app da Guida e informazioni e prima del login su `/help`.
- [Telegram](docs/telegram.md), [account e sicurezza](docs/sicurezza-account.md), [metodi di pagamento](docs/metodi-pagamento.md), [accesso ai gruppi](docs/accesso-gruppi.md).
- [Allegati](docs/allegati.md), [import/export](docs/importazione-esportazione.md), [notifiche](docs/notifiche.md), [modelli e ricorrenze](docs/modelli-ricorrenze-anticipi.md).
- [Backup/ripristino](docs/backup-ripristino.md), [aggiornamenti](docs/aggiornamenti.md), [troubleshooting](docs/troubleshooting.md), [operatività](docs/operativita.md).
- [API](docs/api.md), [database](docs/schema-database.md), [architettura e permessi](docs/architettura-sicurezza.md), [sviluppo](docs/sviluppo.md), [Git e pubblicazione](docs/git.md).
- [Changelog](CHANGELOG.md), [contributi](CONTRIBUTING.md), [sicurezza](SECURITY.md), [contatti e donazioni](docs/contatti.md).

## Una firma dietro ai conti

**Ideato e sviluppato da PjChaosEOW**, con vibecoding e ChatGPT: idee, iterazioni e cura dei dettagli, per condividere le spese con più leggerezza.

Email, repository pubblico e Buy Me a Coffee sono configurabili e rimangono nascosti finché non vengono inseriti recapiti reali. Le donazioni sono interamente volontarie, senza acquisto di funzionalità, obblighi, priorità delle richieste, legami con lo sviluppo del codice o promesse su tempi e risultati.
