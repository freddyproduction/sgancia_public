# Contribuire a Sgancia

Leggere README e ROADMAP prima di proporre modifiche. Descrivere problema, comportamento desiderato ed esempio con soli dati inventati. Non allegare dump reali, chiavi, inviti, password o schermate con informazioni personali.

Usare un branch dedicato e una pull request con problema risolto, cambiamenti e verifiche. Preservare privacy per pubblico, conferma del ricevente, contabilità esatta, idempotenza e controlli di versione. Un ruolo globale non amplia la visibilità delle spese.

Controlli: `python3 scripts/check_git_secrets.py --all`, `python3 scripts/test_git_guard.py`, `python3 scripts/sync_user_guide.py --check`, `npm --prefix frontend test`, `npm --prefix frontend run build`, suite PostgreSQL nel profilo Compose test. Usare esclusivamente istanze e dati sintetici per le prove browser.

Guida nell’app e Markdown derivano da frontend/src/help-content.json: dopo modifiche eseguire scripts/sync_user_guide.py. Non inviare messaggi esterni o automatismi sui dati reali durante i test. Non introdurre dipendenze senza esaminarne manutenzione, vulnerabilità e licenza.

Il progetto è distribuito con licenza AGPL-3.0-only; i contributi devono poter essere distribuiti secondo tale licenza. Non esiste una promessa di accettazione o tempi di sviluppo legata a donazioni.
