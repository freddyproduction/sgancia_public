# Sviluppi futuri richiesti

La roadmap è un elenco di lavoro, non una promessa di date o di funzionalità già disponibili.

## Backup

Il bundle cifrato database/allegati e il ripristino sono già implementati. Restano richiesti il trasferimento completo dell’installazione (definendo copie protette di configurazione e chiavi), la selezione dei singoli gruppi e la personalizzazione di destinazioni, nomi e contenuti. Prima del rilascio servono anteprima del ripristino, conflitti, autorizzazioni, quote e prove isolate di recupero. I backup e le chiavi non entrano nei repository Git.

## Sicurezza e cifratura

Pianificare revisioni e simulazioni di attacco soltanto su ambienti autorizzati e dati sintetici. Documentare rischi, risultati, correzioni e limiti: nessun sistema è dichiarato privo di tutte le vulnerabilità.

La richiesta di impedire al gestore del server di leggere i contenuti richiede uno studio E2EE separato: gestione delle chiavi, più dispositivi, revoca, recupero, condivisione, rivelazioni, calcoli e integrazioni. Non è ottenibile cambiando solo la cifratura del database. Il modello attuale resta privacy applicativa senza E2EE; qualsiasi cambiamento architetturale richiede approvazione prima dello sviluppo dipendente.

## Google e GitHub

Metodi aggiuntivi e facoltativi. Gli account normali Sgancia rimangono con password, MFA e passkey. Configurazione globale dei provider con segreti cifrati; gate e modalità libere/approvazione/invito/disabilitate restano rispettati. Gli utenti esistenti collegano esplicitamente il provider con verifica recente; niente fusione automatica basata sulla sola email. Gestire email private/mancanti, impostazione sicura di una password locale e rimozione dell’ultimo metodo. Definire come applicare la MFA Sgancia agli accessi federati. Proteggere callback, state/nonce/PKCE, token e revoche; provare sospensioni, inviti, approvazioni e indisponibilità provider. Ordine proposto: struttura comune, Google, GitHub, prove e guide.

## Ruoli globali avanzati

Richiesti più superadmin e permessi configurabili per ciascun admin globale, oltre alla scelta del ruolo negli inviti e nelle approvazioni. La revoca riguarda il ruolo, non l’eliminazione dell’account. L’ultimo superadmin deve rimanere protetto. Non sono ancora funzioni rilasciate: il collegamento ai controlli amministrativi richiede autorizzazione alla modifica e verifiche isolate prima della pubblicazione applicativa.
