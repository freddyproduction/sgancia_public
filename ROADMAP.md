# Sgancia — funzionalità e prossimi passi

Aggiornata: 4 novembre 2026 · **0.2.0-dev**. Le caselle completate indicano software consegnato, non prove eseguite su ogni server o dispositivo.

## Disponibile

- [x] Account, MFA, passkey, verifica email, ruoli globali e superadmin fondatore.
- [x] Gruppi, membri/virtuali, inviti con associazione esplicita, ruoli e archivio/cestino.
- [x] Spese composte, più pagatori, sei modalità di divisione, storico e contestazioni.
- [x] Riservate per pubblico, rivelazioni controllate, valute e conversione con anteprima.
- [x] Saldi Smart per gruppo e riepiloghi fra gruppi, rimborsi con conferma del ricevente.
- [x] Allegati, modelli, ricorrenze, anticipi, filtri, statistiche, budget e simulazioni.
- [x] Import/export CSV e JSON, report PDF con controllo della visibilità.
- [x] Notifiche nell’app, email generiche facoltative e Telegram bidirezionale.
- [x] Politiche, audit, backup cifrati, prove di recupero e aggiornamento conservativo.
- [x] Guida integrata, informazioni, proposte e contatti configurabili.

## Presenti ma da configurare o abilitare

| Funzione | Condizione | Dove |
|---|---|---|
| Telegram | Disattivato inizialmente; token e attivazione | Admin globale → Telegram |
| Link ospiti | Disattivati inizialmente | Admin globale → Installazione/link ospiti |
| SMTP | Parametri del proprio server, prova invio reale | Admin globale → SMTP |
| Email notifiche | SMTP + email verificata + preferenze utente | Account e preferenze notifiche |
| Backup automatici/probe | Pianificazione e autorizzazione esplicita | Admin globale → Backup |
| Ricorrenze/rivelazioni | Configurazione dell’autore; sospese dopo restore | Strumenti del gruppo |
| Email sviluppatore, GitHub e donazioni | Valori reali da inserire nel codice; nessun link fittizio | `backend/app/project_info.py` |

## In programma e verifiche aperte

- [ ] PWA e offline completi (blocco 10): il manifest non basta a dichiararli disponibili.
- [ ] OCR locale opzionale (blocco 12).
- [ ] Completamenti grafici e prove accessibilità su Safari/iPhone e VoiceOver.
- [ ] Prove reali passkey Mac/iPhone, consegna SMTP, Telegram e webhook HTTPS.
- [x] Repository GitHub privato e pubblico separati, con pubblicazione sorgenti selezionati.
- [ ] Attestazione completa della CI remota e qualifica della prima release stabile.
- [ ] Qualifica server Linux reale: HTTPS/proxy, LAN, firewall, riavvio e recupero.
- [ ] Revisione indipendente di sicurezza e licenze prima della prima release stabile.

I requisiti non ancora consegnati restano nel perimetro; le attività interne sono tracciate nella TODO di sviluppo. Prima di una release aggiornare questo file e la guida, distinguendo implementazione, abilitazione e prove effettivamente eseguite.

## Nuove richieste di sviluppo

- [ ] Backup completo portabile dell’installazione con procedura di ripristino dedicata: estendere il bundle cifrato DB/allegati già esistente, definendo come gestire configurazione e chiavi senza inserirle in Git.
- [ ] Backup selettivi dei gruppi, con appartenenze, contabilità, allegati e controlli di visibilità; anteprima e conflitti al ripristino.
- [ ] Personalizzare destinazioni, nomi, contenuti e modalità di backup mantenendo quote, percorsi autorizzati e cifratura.
- [ ] Rafforzamento della sicurezza con simulazioni di attacco su ambienti isolati, revisione accessi e dipendenze, recupero e documentazione dei limiti. Nessuna promessa di eliminare ogni vulnerabilità.
- [ ] Studio della cifratura end-to-end per impedire anche al gestore del server di leggere i contenuti: modello chiavi/recupero/condivisione e compatibilità con calcoli, bot, report, ricerca e backup da progettare e approvare. **Non disponibile oggi: la privacy attuale è applicativa.**
- [ ] Accesso e registrazione Google e GitHub aggiuntivi, mantenendo account Sgancia, password/MFA/passkey, gate e policy invito/approvazione. Collegamenti espliciti senza fusione automatica per email; configurazione provider globale e test anti-replay.
- [ ] Più superadmin, ruolo predefinito negli inviti/approvazioni e permessi configurabili degli admin globali: lavorazione richiesta, non ancora rilasciata. Revoca del ruolo tra superadmin senza cancellare account e con protezione dell’ultimo.

Queste voci provengono dalla TODO del titolare e rimangono pianificate finché implementazione e prove non sono completate. Dettagli: [sviluppi futuri](docs/sviluppi-futuri.md).
