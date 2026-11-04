# Troubleshooting

- **Porta 8088 non raggiungibile:** verificare `docker compose ps` e `docker compose logs --tail=100 api migrate db`. Il bind dipende da SGANCIA_BIND_IP; il default è loopback. Sul server verificare bind, firewall e proxy gestiti dall’utente.
- **Readiness non pronta al primo avvio:** completare `docker compose exec api python -m app.cli init`. Se migrate fallisce, non inizializzare tabelle a mano.
- **Chiave richiesta dopo rotazione:** tutti i gate e le sessioni sono revocati; rientrare con la nuova chiave.
- **Sessione che non resta attiva:** verificare l’origine esatta. Per LAN HTTP indicare l’IP con porta in `SGANCIA_HTTP_LAN_ORIGINS`, mantenendo `SGANCIA_SECURE_COOKIES=true` sul server. HTTPS continua a usare cookie Secure. Controllare che Nginx inoltri Host originale e X-Forwarded-Proto=https e che il suo IP reale sia fidato.
- **Origine non autorizzata:** usare host, schema e porta configurati. Alias localhost/127.0.0.1 e altre origini HTTPS in `SGANCIA_ALLOWED_ORIGINS`; soli IP privati HTTP in `SGANCIA_HTTP_LAN_ORIGINS`. `Indirizzo non autorizzato` indica un Host/porta/schema non configurato.
- **Errore CSRF:** ricaricare dopo accesso o cambio sessione; le richieste automatiche devono leggere il cookie CSRF della sessione corrente.
- **Passkey non disponibile:** richiede browser compatibile e HTTPS (o localhost), e l’hostname principale configurato. Le credenziali sono legate al relativo RP.
- **MFA rifiutata:** verificare orario del dispositivo, codice non già consumato e corretta chiave di cifratura dell’installazione. Usare un codice di recupero monouso se necessario. Non disabilitare i controlli per aggirare il problema.
- **Rimborso verso un virtuale:** usare le deleghe e le conferme dei gestori autorizzati; per un ricevente registrato conferma il ricevente.
- **Spesa non divisibile:** controllare somma pagatori, somma quote personalizzate/percentuali e inclusione di tutti i soggetti nel pubblico autorizzato.
- **Backup non decifrabile:** controllare la chiave backup originale e l’integrità del file; non ripristinare output parziali.

Evitare di condividere log con password, cookie, chiavi, dump o contenuti delle spese riservate. Le verifiche del server reale e di Nginx/Cloudflare non sono state eseguite sul Mac.

### Migrazione fallita: password authentication failed

La password POSTGRES_PASSWORD viene usata dall’immagine PostgreSQL solo alla prima inizializzazione. Cambiarla nel .env e ricreare il container non modifica il ruolo già esistente. Ripristinare il valore originale oppure, dopo backup, riallineare esplicitamente il ruolo DB alla nuova password mediante procedura amministrativa che non esponga la password nei log. Non eliminare data/postgres e non eseguire reset del database per correggere un errore di autenticazione. Le chiavi di cifratura applicativa e backup restano quelle originali.

- **Telegram in attesa:** verificare token, abilitazione e Salva e applica nel pannello globale. Il processo parte con Sgancia; nessun comando separato è richiesto. Cambi di configurazione possono richiedere un nuovo collegamento account.
- **Contatti o donazioni assenti:** è intenzionale se le costanti pubbliche in backend/app/project_info.py sono vuote; non sono errori di rete.
- **Guida non allineata:** modificare frontend/src/help-content.json e rigenerare docs/guida-utente.md con scripts/sync_user_guide.py.
