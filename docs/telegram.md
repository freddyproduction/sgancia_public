# Telegram

Il bot è un servizio facoltativo dello stesso Compose. Il web funziona indipendentemente. Disattivato di default: nessuna chiamata Telegram finché un amministratore non abilita l’integrazione.

## Avvio

In Impostazioni installazione → Telegram, inserire il token del proprio bot creato con BotFather, scegliere polling (anche in LAN, nessuna porta aggiuntiva) oppure webhook (richiede origine pubblica HTTPS) e abilitare. Il token è cifrato e non viene restituito dal pannello. Premere **Salva e applica Telegram**: il servizio si avvia già insieme a Sgancia e recepisce automaticamente le impostazioni, senza comandi da terminale. Disabilitare e salvare interrompe le operazioni; il processo rimane in attesa senza chiamare Telegram.

Usare un bot dedicato: il servizio gestisce il suo webhook. Il nome viene verificato con Telegram; il nome facoltativo configurato deve corrispondere. Cambi di token, modalità o autorizzazioni installazione richiedono un nuovo collegamento. Non sono necessari altri container o porte pubbliche.

## Collegare l’account

Aprire il bot dalla Panoramica, inviare `/id`, quindi inserire il proprio identificativo nelle impostazioni account → Telegram. Generare il collegamento dopo aver confermato l’identità sul web e aprirlo entro cinque minuti. È monouso e funziona esclusivamente per l’ID indicato. Non inserire password o chiave globale nella chat.

Dati riservati e notifiche richiedono consensi separati, entrambi inizialmente spenti. Scollegare dal web o con `/scollega` revoca anche le operazioni accodate. Cambio delle credenziali/versione di sicurezza, sospensione account e cambio della chiave d’installazione invalidano l’autorizzazione. Il normale logout web non scollega il bot.

## Operazioni

- `/gruppi`, `/saldi`, `/riepilogo`: gruppi e saldi autorizzati, con collegamenti al web.
- `/spesa`: titolo, data, categoria, pubblico, voci, partecipanti, divisione uguale/percentuale/importi/pesi/quantità e più pagatori. Anteprima e conferma obbligatorie. `/valuta CODICE TASSO` consente il cambio manuale nel wizard.
- `/spese`, `/cestino`: modifica, duplicazione, eliminazione e ripristino con controllo della versione.
- `/foto`: scegliere una spesa, inviare foto/documento e confermare. Si applicano limiti, normalizzazione, quote e permessi degli allegati web. Nessun OCR automatico (blocco 12).
- `/rimborsi`: il debitore può segnalare un pagamento; il ricevente conferma l’incasso e può annullarlo. La segnalazione del debitore non azzera il debito.
- `/notifiche`: aggiornamenti autorizzati. Riepiloghi facoltativi secondo preferenze account/gruppo, fuso e frequenza del blocco 09.
- `/annulla`, `/web`, `/scollega`: interrompere il wizard, aprire il sito, revocare.

Solo chat privata verificata: gruppi, inoltri e messaggi tramite altri bot sono ignorati. Le schermate lunghe rimandano al web (massimo 40 gruppi e 30 spese per elenco). Gestione amministrativa, impostazioni avanzate, autenticazione/passkey, import/export, storico completo e conversione automatica restano sul web. Il bot applica le stesse regole economiche e di visibilità; senza consenso ai riservati mostra soltanto gli ambiti pubblici.

## Sicurezza e gestione

Inbox, bozze e messaggi accodati sono cifrati; codici e pulsanti sono monouso, con scadenza. Replay e clic su vecchie schermate non ripetono le operazioni. Prima di inviare si ricontrollano identità, membri, visibilità e versioni: messaggi divenuti non autorizzati vengono annullati. Retry limitati e deduplicazione dei riepiloghi; il processo usa un lock PostgreSQL per un solo consumatore.

Telegram è un servizio esterno e riceve ciò che si autorizza a inviare. La protezione del contenuto richiesta al provider non impedisce fotografie o copie esterne. Il ripristino di un backup disabilita l’integrazione e cancella collegamenti, bozze, codici e code: abilitare e collegare nuovamente gli account. Fermare anche `telegram` prima del restore. L’aggiornamento guidato avvia sempre il servizio, lasciando invariata l’abilitazione scelta dal pannello.

Verifiche locali con API simulate: collegamento/ID, revoca e versioni sicurezza, replay, webhook, autorizzazioni/private, wizard e quote, allegati e versione, rimborsi, notifiche e retry. Nessun messaggio reale inviato durante lo sviluppo. Restano da provare con il proprio bot la consegna effettiva, le foto da dispositivo e il webhook HTTPS sul server.

Un errore di rete dopo l’invio può causare una risposta duplicata al retry: Telegram non offre una chiave idempotente per sendMessage. Le operazioni finanziarie sono invece deduplicate nel database.
