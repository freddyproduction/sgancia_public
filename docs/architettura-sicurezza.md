# Architettura e confini di sicurezza

Sgancia usa frontend React compilato e API FastAPI nella stessa immagine/origine, PostgreSQL persistente e processi Compose separati per migrazioni, inizializzazione storage, email, automazioni, backup e Telegram. Il servizio Telegram parte con Compose e resta inattivo quando disabilitato. Unica porta applicativa predefinita 8088; DB non pubblicato. API e bot non ricevono il socket Docker.

## Identità e permessi

Il cancello globale è un filtro opzionale, distinto dall’account; è attivo inizialmente. Sessioni HttpOnly, CSRF sulle scritture, origini esatte, rate limit, verifica recente per azioni sensibili, MFA e passkey. Il superadmin fondatore è identificato da ID permanente. Admin globali, proprietari/admin/membri/visualizzatori di gruppo e pubblico della singola spesa sono livelli distinti: un ruolo amministrativo non amplia il pubblico di una spesa riservata.

I servizi verificano appartenenza e pubblico anche per allegati, export, storico, notifiche e bot. Risorse invisibili restituiscono errori senza contenuti privati. Un invito/claim non associa in base al nome; richiede la concessione corretta. Gli ospiti leggono soltanto dati pubblici autorizzati e sono disattivati globalmente inizialmente.

## Contabilità e concorrenza

Importi esatti in unità minime, quote bilanciate, ledger immutabile per revisione e proiezioni sulla revisione corrente. Idempotency-Key per scritture ripetibili, If-Match per modifiche concorrenti; lock di gruppo e transazioni per saldi/rimborsi. Gli ambiti riservati restano separati. Il debitore segnala, il ricevente conferma; un errore di rete non deve creare una seconda operazione economica.

## File, provider e cache

Immagini normalizzate, file limitati/validati, storage privato e download autorizzati. Payload e segreti sensibili cifrati con la chiave installazione; backup con chiave indipendente. Non è E2EE: il gestore di host e chiavi è nel confine di fiducia. Provider SMTP, quotazioni e Telegram sono esterni e configurati esplicitamente; non inviare dati reali per i test.

Le risposte hanno no-store e header di sicurezza; non esiste ancora una cache offline funzionale dichiarata. PWA/offline e OCR rimangono blocchi aperti. Un service worker futuro richiederà revisione separata della revoca e del pubblico dei dati memorizzati.

Telegram verifica ID e chat privata, codici/pulsanti monouso, pin delle versioni di sicurezza e consensi. Inbox/outbox cifrate, replay deduplicato, permessi ricontrollati prima dell’invio. Il restore revoca collegamenti e code e sospende automatismi; le chiavi originali devono essere conservate separatamente.

## Minacce e limiti residui

Proteggere da compromissione host/chiavi, phishing, configurazione proxy errata, file ostili, accessi simultanei, reinvio di richieste e fughe tra pubblici. I test coprono questi controlli applicativi, ma non equivalgono a penetration test indipendente o qualifica del proprio server. Dipendenze, configurazione reale, recupero e dispositivi vanno riesaminati a ogni release. Nessuna attestazione completa di sicurezza è implicita nel blocco 15.
