# Sospendere o eliminare account dalla piattaforma

In **Impostazioni → Superadmin → Gestione utenti e ruoli globali**, un superadmin può sospendere, riattivare o eliminare account ordinari, admin globali e altri superadmin. Ogni operazione richiede la password del superadmin e MFA/recupero se attivo. Gli admin globali ordinari non ricevono questi poteri aggiuntivi.

Non si può sospendere o eliminare il proprio account da questi controlli: deve intervenire un altro superadmin. Deve restare sempre almeno un superadmin attivo; il vincolo è protetto anche dal database. Il riferimento dell’installazione viene trasferito a un altro superadmin attivo prima di sospendere o eliminare quello attuale.

## Sospensione

Blocca l’accesso e revoca le sessioni e i token dell’account. Conserva ruoli, fattori personali, gruppi, conti e storico. Una successiva riattivazione consente un nuovo login; le vecchie sessioni non tornano valide. Un superadmin sospeso conserva il ruolo, ma non può accedere né autorizzare operazioni finché rimane sospeso. Le richieste ancora in attesa si approvano normalmente dal pannello registrazioni.

## Eliminazione

La conferma richiede di scrivere l’email esatta del destinatario. Prima di confermare viene mostrato un riepilogo numerico degli effetti sui gruppi, senza rivelare titoli o contenuti privati.

L’account diventa un’identità anonimizzata non riattivabile. Nome, email, password utilizzabile, immagine, icona, fattori, metodi di pagamento, notifiche personali e collegamenti Telegram vengono rimossi o invalidati. Inviti e codici personali pendenti vengono revocati. Gli account eliminati rimangono riconoscibili nel pannello come Eliminato, per mantenere i riferimenti dello storico.

Le spese, le quote, i rimborsi e gli allegati condivisi non vengono cancellati: i saldi rimangono attribuiti alla persona storica senza account. Nei gruppi dell’account eliminato, la proprietà passa automaticamente a un altro account attivo, preferendo admin, poi membri e infine visualizzatori. Se non ci sono altri account attivi il gruppo va nel cestino. I collegamenti dei gruppi di cui era proprietario sono revocati. Non vengono concessi al superadmin nuovi accessi alle spese riservate.

L’operazione non riscrive i contenuti condivisi o i backup storici già creati. L’eliminazione del profilo non può essere annullata dall’interfaccia; un eventuale ripristino da backup è un’operazione distinta dell’installazione.
