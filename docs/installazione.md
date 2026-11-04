# Installazione

## Requisiti

Docker Engine/Desktop con Docker Compose v2 e spazio persistente per PostgreSQL. Il Mac attuale è esclusivamente ambiente di sviluppo e test. Non viene configurato accesso Internet. Il server reale e il suo reverse proxy sono gestiti dall’utente.

## Configurazione iniziale

**Passaggio obbligatorio prima di build, avvio e bootstrap.** I modelli hanno password e chiavi vuote per evitare credenziali condivise. Copiare il modello non genera i valori.

Dalla cartella del repository sul nuovo server:

```sh
test -e .env || cp .env.server.example .env
```

Per una prova soltanto su localhost si può invece partire da `.env.example`. Se `.env` esiste già, non sovrascriverlo. Non versionare il file. Impostare:

- `POSTGRES_PASSWORD`: password casuale distinta; usare ad esempio un valore esadecimale di almeno 32 byte, senza caratteri riservati URL.
- `SGANCIA_ENCRYPTION_KEY`: chiave Fernet base64 di 32 byte; protegge i segreti TOTP nel database. Conservarne copia di recupero separata.
- `SGANCIA_BACKUP_KEY`: altra chiave base64 di 32 byte, indipendente da quella applicativa.
- `SGANCIA_PUBLIC_ORIGIN`: origine esatta, senza percorso né slash finale.
- `SGANCIA_ALLOWED_ORIGINS`: lista JSON delle altre origini HTTPS e degli alias HTTP localhost/127.0.0.1.
- `SGANCIA_HTTP_LAN_ORIGINS`: lista JSON degli esatti IP LAN HTTP ammessi, inclusa porta. Eccezione distinta dal dominio HTTPS, mai wildcard o IP pubblici.

Generazione chiavi senza installare Python sul server:

```sh
docker run --rm python:3.13-slim python -c 'import secrets; print(secrets.token_hex(32))'
docker run --rm python:3.13-slim python -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
```

Il primo comando genera il valore di `POSTGRES_PASSWORD`. Eseguire il secondo **due volte**: il primo risultato va in `SGANCIA_ENCRYPTION_KEY`, il secondo in `SGANCIA_BACKUP_KEY`. Sono tre valori distinti, da incollare dopo `=` nelle rispettive righe del `.env` usando `nano .env`. Non inserire i nomi dei segnaposto come password. In nano salvare con Ctrl+O, Invio, poi Ctrl+X.

Compilare anche dominio, IP LAN, origini e proxy secondo le sezioni seguenti. La chiave d’accesso iniziale al sito verrà scelta nel bootstrap ed è distinta da queste credenziali tecniche. Conservare una copia protetta delle chiavi, separata dal server; non inviarle in chat o issue. Non usare i valori delle prove automatiche come credenziali reali.

Dopo aver compilato e salvato `.env`:

```sh
chmod 600 .env
docker compose config --quiet &&
docker compose build migrate &&
docker compose up -d &&
docker compose exec api python -m app.cli init
```

Il controllo `config --quiet` non stampa i valori; se fallisce, correggere `.env` prima di proseguire. La sequenza con `&&` si arresta al primo errore. Non usare `docker compose config` senza `--quiet` in output da condividere, perché può mostrare segreti.

**Su un’installazione esistente non generare nuove chiavi né ricopiare il modello per un aggiornamento.** Preservare password DB, chiave applicativa e chiave backup originali. Cambiare il `.env` non cambia automaticamente la password di un database già inizializzato.

## Solo Mac / localhost

```dotenv
SGANCIA_PUBLIC_ORIGIN=http://localhost:8088
SGANCIA_ALLOWED_ORIGINS=["http://127.0.0.1:8088"]
SGANCIA_BIND_IP=127.0.0.1
SGANCIA_PORT=8088
SGANCIA_SECURE_COOKIES=false
```

Il Mac non pubblica nulla in LAN o su Internet. Entrambi gli alias locali sono ammessi esplicitamente. I cookie sulle origini HTTP locali non hanno Secure; su HTTPS mantengono sempre Secure, anche se la configurazione locale legacy indica false. Il flag false globale non è ammesso per installazioni con origine principale esterna.

## Server, dominio e LAN

L’app usa la porta host **8088**, configurabile con `SGANCIA_PORT`. Per renderla raggiungibile in LAN scegliere l’IP privato del server o `0.0.0.0` in `SGANCIA_BIND_IP`, e limitare l’accesso tramite firewall alla rete prevista. Solo la porta applicativa è pubblicabile; PostgreSQL resta interno.

Per il server è disponibile il modello [.env.server.example](../.env.server.example). Sostituire dominio e IP con quelli reali, conservare/generare le chiavi corrette dell’installazione e impostare queste variabili nel `.env` del server:

```dotenv
SGANCIA_PUBLIC_ORIGIN=https://sgancia.tuodominio.it
SGANCIA_ALLOWED_ORIGINS=["http://localhost:8088","http://127.0.0.1:8088"]
SGANCIA_HTTP_LAN_ORIGINS=["http://192.168.1.20:8088"]
SGANCIA_SECURE_COOKIES=true
SGANCIA_BIND_IP=0.0.0.0
SGANCIA_PORT=8088
```

Risultato: dominio HTTPS tramite Nginx, `http://localhost:8088` e `http://127.0.0.1:8088` dal server stesso, `http://192.168.1.20:8088` dagli altri dispositivi LAN. Localhost su un telefono indica il telefono, non il server: da altri dispositivi usare l’IP LAN o il dominio. PostgreSQL resta senza porte pubblicate. Non applicare questo bind al Mac di sviluppo.

Dopo la modifica, dalla cartella del progetto sul server:

```sh
docker compose build migrate
docker compose up -d api
```

L’applicazione e le API sono servite insieme da ogni indirizzo: nessun URL API separato da ricompilare nel frontend. Host/origine/porta devono coincidere con la lista; sono rifiutati indirizzi estranei e richieste POST da un’origine diversa da quella aperta nel browser. Cambiando hostname occorre accedere nuovamente: i cookie sono host-only; account, gruppi e dati restano gli stessi. Non è necessario disabilitare Secure sul dominio per usare HTTP in LAN.

L’eccezione HTTP è consentita soltanto per IP privati RFC1918 o IPv6 ULA dichiarati esattamente. Nessun dominio HTTP o IP pubblico. Il traffico HTTP LAN non è cifrato; restringere l’accesso alla rete locale prevista. Per IP LAN HTTPS usare invece `SGANCIA_ALLOWED_ORIGINS` e il certificato/proxy TLS.

Non viene richiesto o configurato il dominio sul Mac.

Nginx/Tunnel non fanno parte del Compose di Sgancia. L’utente può inoltrare il traffico al server sulla porta 8088. L’esempio in `deploy/` è facoltativo e non viene applicato automaticamente. Configurare gli IP dei proxy fidati in `SGANCIA_TRUSTED_PROXIES` prima di accettare gli header inoltrati. Non usare `*` indiscriminatamente.

Per accedere in LAN senza reverse proxy con TLS, copiare `docker-compose.tls.yml.example` in `docker-compose.tls.yml`, aggiungere in `certs/` certificato e chiave leggibili dall’utente 10001 del container e validi per l’IP/hostname LAN, quindi:

```sh
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Il certificato deve essere riconosciuto dai dispositivi utilizzati. Le passkey sono legate all’hostname configurato come origine principale; usarle tramite quell’hostname. Password e TOTP funzionano anche sulle altre origini autorizzate, inclusa la LAN HTTP esplicita. Le passkey sul dominio non sono trasferibili a localhost/IP; l’app indica l’indirizzo principale quando si tenta di usarle da un alias. Usare lo stesso hostname con DNS locale è l’opzione più semplice per passkey sia in LAN sia da remoto.

## Avvio e primo amministratore

```sh
docker compose build
docker compose up -d
docker compose exec api python -m app.cli init
docker compose ps
```

L’inizializzazione richiede email/nome, password personale di almeno 12 caratteri e chiave globale di almeno 16, senza credenziali predefinite. La registrazione iniziale è soltanto tramite invito. Fino al bootstrap la readiness segnala non pronto: è previsto. Una seconda inizializzazione non sovrascrive l’istanza.

PostgreSQL persiste in `data/postgres/` dentro la cartella del progetto. Non modificare manualmente quei file. Backup in `backups/`, esclusi da Git. Il Compose include mail, automazioni, backup e Telegram (in attesa se disabilitato); non richiedono altre porte. Il bot e gli altri servizi opzionali saranno aggiunti quando implementati.

## Storage privato degli allegati

Compose include storage-init (una tantum, inizializza permessi UID 10001) e monta data/attachments in lettura/scrittura nell’API, mantenendo il resto del filesystem runtime in sola lettura. Nessuna porta storage o DB esposta. Lo storage rimane dentro la cartella progetto ed è escluso dal contesto di build insieme ai dati PostgreSQL. Per i limiti vedere .env.example e [allegati](allegati.md). I backup ora comprendono anche questi file: non copiare il solo volume PostgreSQL come backup completo. Nginx deve ammettere gli upload della dimensione prevista (esempio 12 MiB per file limite 10 MiB).


### Email dell’installazione
Configurare SMTP da Impostazioni → Impostazioni dell’installazione, come amministratore globale. Host, porta, TLS, mittente e credenziali si salvano cifrati nel DB e prevalgono sui parametri opzionali SGANCIA_SMTP_* dell’ambiente. Nessun riavvio richiesto per cambiarli. Il servizio Compose mail gestisce la coda; senza configurazione resta inattivo rispetto agli invii. La prova reale deve essere fatta con “Invia email di prova al mio account”. Guida: [sicurezza account](sicurezza-account.md).

## Prima release e documentazione

Seguire anche [rilascio.md](rilascio.md) per la qualifica Linux/LAN/HTTPS, le due copie Git e le prove ancora aperte. Guida pubblica nell’app su /help; firma e contatti configurabili in backend/app/project_info.py. Non copiare dati o credenziali demo: generare chiavi nuove e completare il bootstrap sul server.
