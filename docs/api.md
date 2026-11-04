# API REST

Documentazione generata dal codice: `/api/docs`, schema `/api/openapi.json`. Versione base `/api/v1`.

L’API è same-origin. Le scritture con sessione richiedono il cookie `sg_session`, il gate `sg_gate` e `X-CSRF-Token` corrispondente a `sg_csrf`. Sono rifiutate origini non autorizzate. I cookie di sessione/gate sono HttpOnly; il token CSRF è leggibile dal client. Nessun CORS permissivo.

- `POST /auth/gate`, `GET /auth/policy`, `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`.
- `/auth/sessions`, `/auth/reauth`, `/auth/totp/setup`, `/auth/totp/confirm`.
- `/auth/passkeys`: opzioni/verifica di registrazione e accesso, elenco, rimozione. Challenge monouso con scadenza; verifica origine, RP, firma e user verification.
- `/admin/users`, `/admin/users/{id}/status`, `/admin/registration`, `/admin/invitations`, `/admin/gate`.
- `/groups`, `/groups/{id}`, `/groups/{id}/participants`, `/groups/{id}/state`.
- `/groups/{id}/expenses/preview`, `/groups/{id}/expenses`, `/groups/{id}/balances`, `/calculator`.
- `PUT /groups/{id}/expenses/{expense_id}` con `If-Match` uguale al numero di versione corrente; `/versions`, `/reveal` con `If-Match`.
- `/groups/{id}/settlements`, `PUT /groups/{id}/settlements/{payment_id}`.
- `/groups/{id}/guest-links`, relativa revoca; `POST /guest/view` senza gate, con token e password nel corpo JSON, mai nella query.
- `/groups/{id}/invitations`, `/invitations/accept`.
- `/groups/{id}/participants/{participant_id}/claim` per emettere un’associazione legata all’email; `/participants/claim` per accettarla.

Le creazioni di spese e rimborsi richiedono `Idempotency-Key` (8–150 caratteri). Stessa chiave e stesso corpo restituiscono la prima risposta; un corpo diverso riceve 409. Le chiavi sono separate per utente, gruppo e tipo di operazione. Versioni in conflitto ricevono 409; risorse invisibili 404; quote invalide 422.

Importi in ingresso come stringhe decimali/espressioni, mai numeri floating point; importi in risposta come interi in centesimi per le valute supportate. I saldi sono raggruppati per pubblico esatto. Le quote di ogni versione bilanciano pagatori e totale; le revisioni precedenti restano immutate e il saldo usa solo la corrente. Un rimborso confermato influisce una volta soltanto.

La rivelazione con rimborsi riservati confermati richiede anteprima e consenso esplicito alla riconciliazione da parte di un gestore incluso nel pubblico. Il vecchio endpoint diretto resta bloccato per questo caso.

Paginazione, account API dedicati e policy di retention delle idempotency key sono ancora da completare prima di un uso su larga scala.

## Estensioni voci e comandi UI

`items[].payers` consente di indicare i pagatori di ogni voce; stringa vuota = anticipo automatico sul resto. Non combinare pagatori per voce con `payers` globale; il formato globale precedente resta supportato. `GET /groups/{id}/expenses/{expense_id}` restituisce la bozza modificabile e conserva gli anticipi globali delle spese precedenti distribuendoli fra le voci senza cambiare il totale di alcuna persona.

`PUT /groups/{id}/participants/{participant_id}`, `PUT /admin/users/{id}`, `GET/POST /groups/{id}/categories`. Le categorie non sono scoperte dalle spese segrete. `POST /groups/{id}/settlements/settle-suggestion` richiede Idempotency-Key e suggerimento corrente esatto; il manager può confermare per virtuali, i registrati confermano personalmente.

## Invito account + gruppo

`POST /groups/{id}/invitations` accetta `registration: true` soltanto per amministratore globale con ruolo gestore nel gruppo, verifica recente ed email destinatario obbligatoria. `participant_id` opzionale associa un virtuale esistente nel medesimo gruppo; anche questo richiede email. Nessuna associazione automatica per nome.

Il token ha una concessione di registrazione e una di gruppo, consumate atomicamente da `/auth/register`, che restituisce `joined_group`. Le policy disabled/approval sono rispettate. `/invitations/accept` rimane disponibile per account già esistenti e consuma anche l’eventuale concessione di registrazione abbinata. I tipi legacy restano validi con i loro permessi originari.

## Finance, impostazioni e cestino

`GET /groups/{id}/finance` restituisce summary (`expenses_total`, `paid`, `owed`, `sent`, `received`, `balance`, `receivable`, `payable`) e transfers consolidati per pagatore/ricevente, composti da quote autorizzate. Le letture usano il lock condiviso del gruppo per essere coerenti con le mutazioni serializzate.

`POST /groups/{id}/settlements/settle-transfer` richiede sender, recipient, components (audience/amount), fingerprint corrente e Idempotency-Key. Le componenti sono validate contro la proiezione autorizzata e registrate/confermate atomicamente, riutilizzando i pagamenti in attesa.

`PUT /groups/{id}` con If-Match della metadata_version modifica name/description/icon e image opzionale (base64 PNG/JPEG/WebP, massimo 2 MB e 16 megapixel, ricodifica WebP 512 px senza metadati). `GET /groups/{id}/image` applica appartenenza al gruppo. Nessun URL remoto o SVG attivo.

`DELETE /groups/{id}/expenses/{expense_id}` con If-Match crea una revisione di eliminazione; `GET /groups/{id}/trash` mostra solo il cestino autorizzato; `POST .../restore` con If-Match crea una nuova revisione e ripristina le allocazioni precedenti. Non ci sono cancellazioni fisiche o annullamenti impliciti dei pagamenti.

## Valute e ripristino rimborsi

- GET `/api/v1/currencies`: valute supportate (tutte a due decimali).
- GET `/api/v1/exchange-rate?base=USD&quote=EUR`: quotazione firmata con token, rate, date, source. Ultimo riferimento giornaliero BCE tramite Frankfurter v2; cache 1h. Errore 503 senza fallback obsoleto se fonte indisponibile, coppia validata prima della rete.
- POST `/api/v1/currency-conversion`: `{amount,base,quote,token?,rate?}`. Calcolatore esatto per controvalore immediato; nessuna scrittura contabile.
- ExpenseIn: campi opzionali `currency`, `exchange_token`, `exchange_rate`. Stessa unità minima per valute supportate. Valuta originale diversa da quella del gruppo richiede tasso. Anteprima restituisce `conversion`; resolved items conservano original_amount_minor e conversion. Nessuna conversione esterna ad ogni salvataggio: token acquisito prima, firmato e congelato.
- PUT `/api/v1/groups/{id}/currency` con If-Match metadata_version e `{currency,exchange_token?,exchange_rate?}`. Solo owner/admin, gruppo attivo. Converte tutte le spese e i rimborsi in transazione; nessuna divulgazione dei dati riservati nel risultato. Arrotondamento per voce ai centesimi con allocazione riconciliata; revisioni precedenti conservate.
- POST `/api/v1/groups/{id}/settlements/{sid}/undo`: ripristino del debito relativo a rimborso confirmed; diventa cancelled, aggiunge evento, ripetibile senza doppio effetto. Solo ricevente o manager per destinatario virtuale. Un vecchio retry settle-transfer non può riattivare un rimborso annullato.
- settle-suggestion e settle-transfer: normale membro deve essere destinatario, il debitore riceve 403. Registrazione manuale POST settlements rimane pending. Fingerprint trasferimenti include valuta per rifiutare suggerimenti precedenti al cambio valuta.

## Accessi multipli alla stessa applicazione

`SGANCIA_PUBLIC_ORIGIN` indica l’origine principale (anche RP passkey); `SGANCIA_ALLOWED_ORIGINS` elenca HTTPS e alias loopback; `SGANCIA_HTTP_LAN_ORIGINS` ammette esclusivamente gli esatti IP privati HTTP dichiarati. Frontend e API condividono ogni origine. Middleware controlla Host/schema/porta prima di servire dati, Origin della scrittura deve coincidere col target. Non viene abilitato CORS. Health GET/HEAD restano disponibili per i controlli Docker. Cookie host-only, HttpOnly per gate/sessione, SameSite Strict; Secure sempre su HTTPS e rimosso solo per loopback/LAN HTTP dichiarati. Passkey da alias: 400 con messaggio che indica l’origine principale, senza cambiare RP/verifiche crittografiche.

## Preferenza tema dell’account

PUT `/api/v1/auth/preferences` con `{"theme":"light"}` oppure `{"theme":"dark"}`. Richiede sessione, gate e CSRF correnti; nessun identificatore account accettato nel corpo. Risponde con user_out aggiornato, incluso theme. GET auth/me e risposte login/passkey contengono la stessa preferenza. Default iniziale light; scelta condivisa da tutte le sessioni dello stesso account. Nessuna modifica a nome, ruoli, password o stato.

## Allegati, Smart e panoramica generale

- GET `/api/v1/groups/{gid}/attachment-limits`: limiti non sensibili (file, numero, quota personale nel gruppo).
- GET/POST `/api/v1/groups/{gid}/{kind}/{target}/attachments`, kind expenses o settlements. POST corpo binario, X-Filename percent-encoded e Idempotency-Key; tipo reale validato dal contenuto. Risultato con ID, nome canonico, MIME, dimensione, anteprima e revisione.
- GET `/groups/{gid}/attachments/{aid}/content`: download forzato application/octet-stream con filename UTF-8 e CSP sandbox; GET `/preview`: sola immagine JPEG ricodificata.
- DELETE `/groups/{gid}/attachments/{aid}` e POST `.../{aid}/restore`: rimozione reversibile e ripristino autorizzati. Parent e pubblico verificati ad ogni operazione; file mancanti/danneggiati restituiscono 503.
- GuestIn aggiunge show_attachments, default false; richiede show_names e show_details. guest/view restituisce solo allegati pubblici consentiti e file_access firmato temporaneo. POST `/guest/attachments/{aid}` con token, password, view_token e preview opzionale; scadenza/revoca sempre ricontrollate. Nessun accesso ospite alle ricevute dei rimborsi.
- GroupOut aggiunge smart_balances. PUT `/groups/{gid}/smart-balances` con `{"enabled":true|false}` e If-Match metadata_version: solo manager attivo, default true, cambia proiezioni e non il ledger storico. Smart disattivo conserva debiti per voce/spesa e compensa solo la coppia, sempre per ambito.
- GET `/api/v1/overview`: totals per valuta con receive/pay e people raggruppate per identità, direzione e valuta, dettaglio gruppi, fingerprint e permesso di ricezione. Nessuna somma tra valute né unione dei virtuali per nome.
- POST `/api/v1/overview/settle` con key/fingerprint e Idempotency-Key: solo ricevente autorizzato in tutti i gruppi coinvolti. Importi derivati e rivalidati dal server; lock gruppi ordinati, una transazione per tutti i rimborsi. Conflitto o errore annulla tutto. Replay dopo undo non riconferma il pagamento. I gruppi in sola lettura restano consultabili ma impediscono il saldo globale di quella riga.


### Cestino dei gruppi
- DELETE `/api/v1/groups/{id}`: solo proprietario, If-Match metadata_version; eliminazione reversibile per tutti e revoca inviti/link/claim.
- GET `/api/v1/group-trash`: gruppi eliminati di cui l’utente è proprietario.
- POST `/api/v1/groups/{id}/restore`: solo proprietario, If-Match; ripristina dati e stato, conserva le revoche.


### Blocchi 02 e 03
Tutti i percorsi seguenti sono sotto `/api/v1`. Regole complete in cronologia-e-membri.md.

- GET `/groups/{gid}/expenses/{eid}/history`: versioni autorizzate, differenze, autore/data, valuta/conversione e contestazioni. Anche `/versions` applica il filtro storico.
- POST `/groups/{gid}/expenses/{eid}/disputes`: reason, If-Match versione spesa.
- PUT `/groups/{gid}/expenses/{eid}/disputes/{did}`: status resolved/rejected/withdrawn e reason.
- POST `/groups/{gid}/expenses/{eid}/preview`: anteprima di modifica con partecipanti storici e quotazione conservata.
- GET `/groups/{gid}/settlements/{sid}/history`: eventi motivati e conversioni. PUT rimborso accetta reason; contestazione e uscita dallo stato disputed la richiedono.
- POST `/groups/{gid}/ownership`: target, If-Match metadata_version, identità recente.
- POST `/groups/{gid}/ownership/{oid}/accept`: identità recente, account destinatario.
- GET `/groups/{gid}/participants/{pid}/departure-preview`; POST stesso percorso `/depart` con fingerprint e keep_balance.
- POST `/groups/{gid}/participants/{pid}/reactivate`: riattiva virtuale, nessun account automaticamente associato.
- POST `/groups/{gid}/merge/preview`: source/target. POST `/merge`: stessi dati e fingerprint.
- GET `/groups/{gid}/operations`: metadati autorizzati e azioni disponibili. POST `/operations/{oid}/undo-merge`: ripristino solo con stato successivo invariato.
- GET/POST `/groups/{gid}/delegations`: elenco autorizzato o concessione virtual_id/delegate_id/pay/attest/days. DELETE `/delegations/{did}` revoca.
- Claim esistente POST `/groups/{gid}/participants/{pid}/claim` (email) e POST `/participants/claim` (token), ora con UI dedicata e revoca dei codici precedenti.

Dettaglio partecipanti include active e merged_into. Le persone uscite/unite restano identificabili nello storico ma non acquistano accessi o nuove quote per default.


### Account, SMTP e metodi di pagamento (blocco 04)

- GET `/auth/entry-policy`: stato pubblico del gate; politica registrazioni restituita solo se gate disabilitato.
- PUT `/auth/password`: password corrente, new_password e codice MFA/recupero se attivo; revoca altre sessioni.
- PUT `/auth/email`: email nuova, password e MFA; azzera verifica, revoca altre sessioni e accoda verifica se SMTP disponibile.
- GET `/auth/email/status`, POST `/auth/email/send-verification`, POST `/auth/email/verify` con token.
- POST `/auth/password/forgot` con email: risposta non enumerativa. POST `/auth/password/reset`: token, new_password e codice MFA/recupero se attivo; revoca tutte le sessioni.
- POST `/auth/mfa/recovery-codes`, `/auth/mfa/disable`, `/auth/mfa/rotate`: password e fattore corrente. POST `/auth/mfa/rotate/confirm`: password e codice del nuovo autenticatore.
- GET/PUT `/admin/access-policy`: solo admin globale; PUT enabled richiede identità recente e revoca sessioni/concessioni.
- GET/PUT `/admin/installation/smtp`: configurazione SMTP, solo admin globale. PUT richiede identità recente; password null/vuota conserva il segreto, clear_password elimina esplicitamente. GET restituisce password_set, mai password. Credenziali cifrate nel DB.
- POST `/admin/installation/smtp/test`: identità recente, messaggio accodato verso il solo account admin corrente.
- GET/POST `/account/payment-methods`: elenco/creazione personale. PUT/DELETE `/account/payment-methods/{id}` con If-Match; GET `/account/payment-methods/{id}/image` autorizzato al titolare.
- GET `/groups/{gid}/participants/{pid}/payment-methods` e `/{id}/image`: solo metodi condivisi del creditore con email verificata, richiedono un trasferimento visibile dal richiedente al destinatario nel gruppo. Nessuna eccezione manager/ospiti.

Le risposte account aggiungono email_verified. Gli errori di validazione restituiscono loc/msg/type senza input/ctx, per non riflettere password o configurazioni complete.


### Assegnazione ruolo globale
PUT `/api/v1/admin/users/{id}/global-role`: enabled, expected_admin, password del richiedente e code MFA/recupero quando attivo. Solo admin globale con identità recente. Account attivo per promozione, ultimo admin attivo protetto con lock dell’installazione condiviso da modifica/sospensione utenti. Risposta admin/login_required/sessions_revoked. Ruoli e pubblici dei gruppi invariati; audit global_admin.granted/revoked.


### Superadmin
Le risposte account e GET admin/users includono superadmin, derivato dal riferimento dell’installazione, non modificabile dai payload. PUT global-role rifiuta la revoca del fondatore; status e modifica account rifiutano le operazioni degli altri admin sul superadmin. Il fondatore cambia email dal proprio percorso /auth/email con password/MFA. Nessun endpoint per cambiare il fondatore o assegnare il titolo ad altri.


### Recupero amministrativo dei fattori
POST `/api/v1/admin/users/{id}/reset-factors`: password/code dell’amministratore corrente, remove_mfa, remove_passkeys e confirm_reset=true. Solo admin globale attivo con identità recente; almeno un fattore selezionato. Target superadmin e target uguale all’operatore rifiutati. Cancella i soli fattori selezionati, revoca sessioni/challenge/token temporanei del destinatario, mantiene password/email/status/admin/ruoli gruppo. Audit account.mfa_admin_reset e account.passkeys_admin_reset, risposta con conferma e conteggio chiavi rimosse; nessun segreto restituito. Limite cinque richieste ogni cinque minuti per operatore, CSRF/origini conservati.

## Import/export (blocco 07)

GET /groups/{gid}/export?format=csv|json|pdf supporta q/start/end/category/tag/person e include solo dati autorizzati. GET /imports/csv-template fornisce il modello semplice. POST /groups/{gid}/imports/preview riceve format/content/mapping/rates e restituisce anteprima cifrata legata al partecipante; POST /groups/{gid}/imports/{id}/apply riceve selected/force_duplicates/confirm, con salvataggio atomico e ripetizione idempotente. POST /guest/export usa token/password nel body e formato, richiede show_exports e applica le stesse redazioni del link; successo consuma un’apertura, errori no. Vedi docs/importazione-esportazione.md per schema e limiti.

## Catalogo aggiornato

Tutti i percorsi e metodi, inclusi bot, impostazioni operative e informazioni pubbliche: [api-reference.md](api-reference.md), generato dal codice. `/api/v1/project` espone soltanto versione, firma e recapiti pubblici configurati, senza dati degli account o segreti. Le proprietà delle richieste/risposte sono nello schema OpenAPI corrente, non in snapshot manuali.
