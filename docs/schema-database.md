# Schema database implementato

Migrazioni Alembic versionate in `backend/migrations/versions`; modelli in `backend/app/models.py`.

- `instance`: gate hash, versione revoca, politica registrazioni.
- `users`, `sessions`, `gate_grants`, `recovery_codes`, `rate_buckets`, `audit_events`, `invitations`.
- `passkeys`, `webauthn_challenges`: chiavi pubbliche, contatori, challenge monouso.
- `groups`, `participants`: ruolo per partecipante, account opzionale, isolamento per gruppo.
- `expenses`, `expense_versions`, `ledger_entries`: testa corrente, snapshot delle revisioni, quote/anticipi immutabili per revisione.
- `settlements`, `settlement_events`: stato di pagamento, conferma del ricevente e cronologia.
- `idempotency_records`: deduplicazione separata per utente/operazione/gruppo e hash della richiesta.
- `guest_links`, `group_invitations`, `participant_claims`: token hash, limiti e collegamenti controllati.

Foreign key composte nel ledger e nei rimborsi impediscono riferimenti a partecipanti di un altro gruppo. Totale e quote sono interi in unità minime; le quattro valute iniziali hanno due decimali. Ogni revisione della spesa produce quote bilanciate; le aggregazioni selezionano esclusivamente la revisione corrente. Le revisioni precedenti non vengono cancellate.

Il modello completo previsto rimane in `brain/03-modello-dati.md`. Le tabelle Telegram sono implementate (stato, collegamenti, concessioni, inbox, azioni e outbox cifrate); importazione/esportazione del blocco 07 disponibile. Storage, outbox email, ricorrenze, deleghe e fusioni sono presenti. Il fatto che siano descritte nel brain non significa che esistano nel database.

Aggiornamento: groups include description/icon/image binaria WebP e metadata_version. expenses include deleted per il cestino reversibile. ExpenseRevision registra anche eliminazioni/ripristini; Entry conserva le versioni precedenti. Le immagini dei gruppi sono nel DB e quindi già incluse nei dump cifrati; gli allegati delle spese sono nello storage privato incluso nel bundle di backup.

## Storico cambio valuta principale

`currency_changes`: id, group_id, actor_id, snapshot JSON, created. Snapshot conserva quotazione, riferimenti alle revisioni prima/dopo e importi dei rimborsi prima/dopo. Nessun endpoint di consultazione globale; backup PostgreSQL include la tabella. Le nuove revisioni spesa alla conversione contengono importi esatti nella nuova valuta; precedenti revisioni mantengono importi/valuta/tasso originali. Le nuove spese possono conservare nei snapshot valuta originale e token firmato; i resolved items contengono controvalore e metadati conversione.

## Tema per account

users.theme: String(5), non nullo, vincolo light/dark. Default ORM light; migrazione a18e9bf24601 inizializza gli account esistenti a light e poi rimuove il default server. Campo incluso nel backup DB, non in storage separato del browser.

## Allegati e Smart (b65d3ea41902)

Group.smart_balances boolean inizializzato true; GuestLink.show_attachments inizializzato false. Attachment: id, group_id, expense_id+expense_revision oppure settlement_id (vincolo esclusivo), uploader_id, storage_key opaca unica, filename, media_type, size, preview_size, sha256, deleted e created. FK verso la revisione originaria della spesa, indici per gruppo e parent. I dati binari sono nel volume privato data/attachments, non nella tabella. Il downgrade rifiuta di eliminare metadati quando esistono allegati. I saldi consolidati della panoramica sono proiezioni, non un secondo ledger; le ricezioni generano i normali Settlement/SettlementEvent nei gruppi originari.


## Migrazione d790e321ab04

participants.active (boolean, default applicativo true) conserva le identità inattive; merged_into conserva il riferimento logico alla destinazione della fusione senza cancellare le righe storiche. Uscita: user_id disassociato dopo snapshot tracciato nell’operazione, nessuna cancellazione di ledger/documenti.

expense_disputes collega spesa/versione e partecipante, motivazione, stato, risolutore ed esito/data. group_operations conserva snapshot strutturali, proposte e rettifiche controllate; gli snapshot economici non vengono esposti dal riepilogo delle operazioni. virtual_delegations registra virtuale, delegato, permessi pay/attest, scadenza, revoca e account concedente. settlement_events aggiunge reason e ordinal per eventi motivati e ordinamento dei nuovi eventi.

La fusione crea nuove expense_versions e ledger_entries, non riscrive le revisioni precedenti. Rimborsi aggiornati conservano identità precedenti nella snapshot dell’operazione e aggiungono eventi. Undo crea ulteriori revisioni, con impronta dello stato successivo per impedire sovrascritture.


## Migrazione e82d4195ca06

Instance aggiunge gate_enabled (true iniziale) e smtp_config cifrata/nullable. User aggiunge email_verified (false iniziale senza blocco retroattivo) e auth_version (1); Session aggiunge auth_version (1). Revoche sensibili incrementano la versione dell’account, aggiornando solo l’eventuale sessione corrente da conservare.

account_tokens conserva soltanto hash del token, account, email vincolata, finalità, versione, scadenza e consumo. mail_messages conserva payload cifrato, riferimento hash del token quando presente, scadenza, stato e tentativi/prossimo retry; mail worker scarta token superati/scaduti e non registra dati dei messaggi nei log. payment_methods conserva owner, istruzioni cifrate, immagine privata normalizzata, condivisione esplicita e versione per conflitti. Entrambi i payload e SMTP richiedono la stessa chiave applicativa originale anche dopo il ripristino.


## Migrazione f913a762bd08

instance.superadmin_id nullable prima del bootstrap, FK users.id con ON DELETE RESTRICT. Una volta inizializzata, l’installazione mantiene un riferimento immutabile al fondatore. Trigger PostgreSQL proteggono ID, admin=true e status=active dell’account referenziato, oltre a sostituzione/azzeramento del riferimento e cancellazione della riga installazione. Bootstrap crea/flush il primo User e salva il riferimento nello stesso commit; migrazione assegna il fondatore legacy solo se identificato senza ambiguità o esplicitamente verificato dall’operatore. Audit installation.initialized e installation.superadmin_assigned, nessun nome/email codificato nel software.

## Blocco 05 — fa05a762bd09

`expense_plans` conserva autore/partecipante autorizzante, gruppo/valuta, bozza, pubblico, versione, calendario e stato. `expense_jobs` conserva data univoca per piano, pubblico dell’esecuzione, stato, tentativi, prossimo retry ed eventuale spesa generata. Il worker usa i lock del gruppo e transazioni atomiche; non richiede una coda esterna. `settlements.kind/note` distinguono anticipi e rimborsi, mantenendo il ledger e gli eventi esistenti. Tag e consenso alle espressioni risiedono negli snapshot revisionati delle spese.

## Blocco 06 — fb06a762bd10

`budgets`: gruppo, creatore/partecipante, pubblico o personale, limite/valuta, soglia, periodo, categoria/tag e versione. Pubblico: spese pubbliche totali; personale: quota dell’account nelle sole spese visibili. `final_reports`: snapshot autorizzato, creatore e partecipante storico, data; lettura vincolata all’account e all’appartenenza attiva con il medesimo partecipante. Simulazioni interamente in memoria; nessuna tabella simulazioni o rettifica del ledger. La chiusura archivia il gruppo e salva il report dell’owner, senza accedere ai segreti esclusi.

## Blocco 07 — fc07a762bd11

`guest_links.show_exports`: default false per i link preesistenti, consenso esplicito nei nuovi link. `import_batches`: account/gruppo/partecipante, valuta, payload cifrato, scadenza, flag applied ed esito; dopo applicazione rimane un payload vuoto cifrato. `imported_expenses`: provenienza hash, gruppo/partecipante ed expense_id, vincolo unico per gruppo/partecipante/origine. Non contiene identità degli account di origine. Gli snapshot spesa possono conservare `exchange_context` con base/quote/rate/source/date dichiarati, sempre etichettati importati nel controvalore e nello storico. Nessuna tabella export persistente: file generati in memoria.

`ExpenseRevision.snapshot.allocation_order` conserva il criterio dei pareggi nei maggiori resti per il trasferimento nativo fra gruppi: i riferimenti vengono rimappati senza riassegnare centesimi. La rivelazione/duplicazione e l’editor riconciliano i riferimenti correnti; non contiene osservatori esclusi dal nuovo pubblico. Nessuna nuova tabella per questo metadato.

Catalogo completo di tabelle, colonne, tipi e riferimenti: [database-reference.md](database-reference.md), generato da scripts/export_reference.py senza leggere dati. Architettura e confini: [architettura-sicurezza.md](architettura-sicurezza.md).
