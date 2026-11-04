# Aggiornamenti che conservano i dati

Non c’è ancora una release stabile né un servizio remoto di auto-aggiornamento. Il codice viene scelto dall’operatore; non viene scaricato o eseguito dal pannello web. Non cancellare `data/`, `backups/` o `.env` e non ricreare l’installazione come se fosse nuova.

1. Leggi changelog e compatibilità. Conserva una copia fuori server del backup e delle chiavi originali.
2. Acquisisci nella cartella del progetto la versione sorgente verificata, mantenendo configurazione e dati locali esclusi da Git.
3. Esegui `bash scripts/update.sh`: crea un backup cifrato, ferma api/mail/worker/backup/telegram, costruisce l’immagine condivisa con il servizio migrate, applica le migrazioni, esegue Alembic check, riavvia e controlla la disponibilità.
4. Da web verifica accesso, schema compatibile, gruppi, saldi e ultimo backup. Riattiva pianificazioni solo se necessario.

Il database persistente resta nella stessa cartella; le migrazioni aggiungono/trasformano lo schema senza una nuova inizializzazione. Le prove QA hanno conservato lo stesso partecipante associato e il ledger. Non usare `down -v`, eliminazioni della cartella dati o bootstrap demo per aggiornare un server esistente.

Se build/migrazione falliscono, non fare downgrade distruttivi e non sostituire credenziali: i servizi applicativi restano fermi per il controllo. Ripristina il codice compatibile con il backup e usa la procedura esplicita di recupero in `backup-ripristino.md`, che sostituisce lo stato soltanto dopo conferma. In caso di errore disponibilità dopo l’avvio, controlla `docker compose ps` e i log locali; nessun rollback dei dati è eseguito automaticamente.

Il web non monta il socket Docker. Il nuovo servizio backup usa una directory distinta, senza nuove porte. La prova completa dello script è stata eseguita su Compose QA il 4 novembre 2026; restano le verifiche sul server reale e le future procedure di rilascio pubblico del blocco 15.

Il servizio Telegram viene avviato insieme agli altri, rimanendo inattivo se l’admin non l’ha abilitato. La guida /help e le informazioni pubbliche seguono la versione dell’immagine installata; per modificare i recapiti pubblici cambiare backend/app/project_info.py e applicare l’aggiornamento ordinario.
