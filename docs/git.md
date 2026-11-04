# Git del progetto

Repository locale nella directory master `/Users/freddy/Desktop/Hobby/sgancia`. L’installazione Docker continua a usare questa stessa cartella.

- `main`: checkpoint verificati del software, non una dichiarazione che l’intero prodotto sia finito.
- `develop`: branch di lavoro per i prossimi blocchi.
- `feature/blocco-07-import-export` (esempio): branch temporaneo per una funzione; dopo i test viene integrato in `develop`, poi in `main` quando pronto.
- `checkpoint-blocco-06`: tag annotato del primo stato versionato, comprendente lo sviluppo disponibile fino al blocco 06. Il blocco 04 conserva le prove esterne SMTP/passkey ancora aperte.

Non esiste una storia Git precedente ricostruibile: il primo commit fotografa il progetto esistente. Non vengono inventati commit retroattivi per i blocchi passati.

## Procedura

```sh
git switch develop
git switch -c feature/nome-attivita
# modifiche e verifiche pertinenti
git add PERCORSI_SPECIFICI
git diff --cached --stat
git diff --cached --check
git commit -m "feat: descrizione concreta"
git switch develop
git merge --no-ff feature/nome-attivita
# quando verificato e pronto
git switch main
git merge --ff-only develop
git switch develop
```

La copia corrente usa `.githooks/pre-commit`: controlla i file effettivamente nell’indice, i valori sensibili dell’ambiente locale, chiavi private/token riconoscibili e gli esempi `.env`. Il controllo non stampa valori segreti. Dopo una nuova clonazione attivarlo con `git config core.hooksPath .githooks`. È una protezione aggiuntiva, non una garanzia di rilevare qualsiasi segreto: controllare sempre cosa viene versionato.

`.env`, dati PostgreSQL, allegati, backup, credenziali, certificati, cartella `.local`, dipendenze e build sono esclusi. L’esempio server è stato ripulito; l’originale contenente una vecchia configurazione è conservato soltanto in `.local/server-example-original-private.txt`, con permessi privati e fuori da Git. Non copiarlo sul server o pubblicarlo.

Git salva sorgenti e documentazione, **non sostituisce il backup del database e degli allegati**. Prima di cambiare branch con schemi diversi fermare i servizi, salvare il backup e verificare la compatibilità delle migrazioni. Non fare reset distruttivi o downgrade per ritornare a un vecchio commit su dati in uso.

Nessun remoto è configurato e nessun codice è stato pubblicato. Quando sarà scelto un repository remoto, collegarlo esplicitamente e trasferire soltanto la storia controllata. Non includere dati o segreti nei comandi o negli URL del remoto.

Checkpoint successivo: `checkpoint-blocco-07`, sviluppo del blocco 07 su `feature/blocco-07-import-export`, verificato e integrato in develop/main. La gestione locale continua senza remoto né pubblicazione.

## Separare sviluppo e pubblicazione

La copia di sviluppo conserva la storia verificata, la TODO e il brain nella cartella master. Per la copia pubblica usare `scripts/prepare_public_repository.py` dopo il commit: esporta soltanto i file versionati ammessi in una nuova cartella sotto `.local/publication`, inizializza un Git separato senza storia privata e non effettua push. Il repository pubblico resta senza commit finché il titolare non sceglie la propria identità/email pubblica; non viene inventato un recapito.

Le due destinazioni remote devono essere scelte dal titolare. Non usare il repository privato come deposito di `.env`, database, allegati o backup: il backup completo dell’installazione rimane cifrato e separato da entrambi i repository. La pubblicazione e la CI remota non sono attestate dalle sole prove locali. Vedere [rilascio.md](rilascio.md).

## Repository remoti scelti dal titolare — 4 novembre 2026

Sviluppo: https://github.com/freddyproduction/sgancia_dev.git (privato verificato via API GitHub). Pubblico: https://github.com/freddyproduction/sgancia_public.git (pubblico verificato). Entrambi inizialmente vuoti; accesso push verificato. Il titolare ha autorizzato collegamento e caricamento. Copia pubblica locale in .local/publication/sgancia-public, senza storia privata. Conservare main/develop e tag nel remoto privato; il pubblico ha la propria main e revisioni selezionate. Nessun dato/configurazione/backup nel Git. Per futuri aggiornamenti controllare le differenze nella copia pubblica e fare commit normali, mai sovrascrivere la cronologia remota con force-push.

Caricamento iniziale completato il 4 novembre 2026: main/develop e checkpoint nel privato; prima main pubblica con tag v0.2.0-dev, senza storia privata. Identità commit pubblici PjChaosEOW con indirizzo no-reply GitHub, senza pubblicare l’email personale. Riferimenti remoti confrontati. CI pubblica avviata, esito non ancora attestato; i futuri push main/develop e pull request avviano i controlli, i tag storici non li moltiplicano.
