# Sicurezza

Sgancia è in sviluppo attivo e non dispone ancora di una release stabile qualificata su server reale. Le verifiche automatiche non equivalgono a una revisione indipendente.

Non pubblicare vulnerabilità insieme a dati privati, credenziali o procedure contro installazioni altrui. Preparare una descrizione con versione, prerequisiti, impatto e riproduzione su dati sintetici. Usare il contatto privato reale dello sviluppatore quando configurato in Guida e informazioni; finché manca, conservarla e richiedere un canale privato senza pubblicare i dettagli sensibili.

La privacy è applicativa, non end-to-end: chi amministra server e chiavi ha capacità tecniche sui dati. SMTP, quotazioni e Telegram sono integrazioni esterne esplicite. Allegati e report rispettano il pubblico corrente; nessuna cache offline completa è dichiarata disponibile.

Proteggere host, chiavi e backup; mantenere Docker e dipendenze aggiornati. Non pubblicare direttamente PostgreSQL. Configurare origini esatte e proxy fidati senza wildcard, HTTPS sul dominio e accesso LAN limitato alla rete scelta. Non disabilitare globalmente i cookie Secure per risolvere la LAN.

Dopo restore controllare utenti, saldi e pianificazioni: sessioni/inviti sensibili vengono revocati e automatismi sospesi secondo le guide. Non effettuare downgrade distruttivi sul database in uso.
