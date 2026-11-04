# Sviluppo

Cartella master unica: `/Users/freddy/Desktop/Hobby/sgancia`. Leggere `AGENTS.md` e `brain/` prima di proseguire. La precedente cartella temporanea è stata rimossa.

L’applicazione gira interamente in Compose. Per modificare sorgenti si possono utilizzare gli ambienti locali `.venv/` e `frontend/node_modules/`, conservati nella stessa cartella, oppure costruire con Docker. Non sono prerequisiti del server.

## Test interamente in Compose

```sh
docker compose --profile test run --build --rm test
docker compose --profile test stop db-test
docker compose --profile test rm -f db-test
```

Il database test è separato, senza porte pubblicate e in memoria; non usa il database applicativo. Il runner verifica anche il ciclo completo delle migrazioni. Le credenziali fisse di questo servizio appartengono soltanto al test isolato e non inizializzano account o database di produzione.

## Verifiche locali

```sh
cd backend
../.venv/bin/python -m pytest -q
# Per usare PostgreSQL, definire SGANCIA_TEST_DATABASE_URL verso un DB di test dedicato.
# ATTENZIONE: la fixture crea e rimuove tutte le tabelle del DB di test!
cd ../frontend
npm ci
npm test
npm run build
```

La suite senza variabile usa SQLite per i test veloci; la prova dei lock concorrenti viene saltata. PostgreSQL è obbligatorio per verificare comportamento reale, vincoli e transazioni. Mai puntare la suite a database con dati da conservare.

La CI configura PostgreSQL dedicato, esegue test, upgrade/check/downgrade Alembic, test frontend e build. Il file workflow è presente, ma non è stato eseguito su GitHub: repository remoto non configurato.

Versioni Python 3.13 e Node 24 in Docker. `backend/requirements.lock` include versioni/hash multipiattaforma; `requirements-dev.lock` è l’ambiente di sviluppo verificato. `frontend/package-lock.json` fissa le dipendenze del client. Prima di aggiornare le librerie rieseguire controlli pertinenti e rigenerare i lock.

Le passkey sono testate con firme crittografiche reali prodotte da un autenticatore simulato: verifica hardware/dispositivi mobili resta da eseguire. Non sostituire la verifica delle firme con un mock.

## Verifiche dei blocchi 15/16

- `python3 scripts/sync_user_guide.py --check`: guida nell’app e Markdown dalla stessa fonte.
- `.venv/bin/python scripts/export_reference.py --check`: cataloghi API/database generati dal codice senza leggere dati.
- Dopo la build dell’immagine: `python3 scripts/run_browser_qa.py`. Genera chiavi nuove, usa solo il progetto Compose sgancia-release-qa e loopback 18088, verifica guida mobile/tema, login, spesa/anteprima/saldi, letture concorrenti, recupero rete e restart con persistenza. Rimuove soltanto il proprio ambiente; nessuna prova sui dati reali.
- La CI include i medesimi percorsi browser, ma la sua esecuzione remota va attestata sul repository scelto dal titolare.

Gli inventari di licenze e gli audit delle dipendenze sono descritti in dipendenze-licenze.md. Ripeterli prima di ogni rilascio. La checklist del server reale è in rilascio.md.
