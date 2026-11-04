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
- [ ] CI su remoto scelto dal titolare; pubblicazione GitHub e destinazione privata separata.
- [ ] Qualifica server Linux reale: HTTPS/proxy, LAN, firewall, riavvio e recupero.
- [ ] Revisione indipendente di sicurezza e licenze prima della prima release stabile.

I requisiti non ancora consegnati restano nel perimetro; le attività interne sono tracciate nella TODO di sviluppo. Prima di una release aggiornare questo file e la guida, distinguendo implementazione, abilitazione e prove effettivamente eseguite.
