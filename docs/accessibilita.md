# Accessibilità — blocco 13A

Aggiornamento del 4 novembre 2026. Popup nativi `dialog` in un portale, sfondo reso inerte dal browser, titolo associato, focus iniziale sul titolo, Escape limitato al popup superiore e ritorno al comando di apertura. Le finestre lunghe restano centrate e scorrono internamente. Le selezioni di sezione usano pulsanti con stato premuto, senza dichiarare un comportamento ARIA tab non implementato.

Aggiunti salto al contenuto/modulo di accesso, nome della navigazione, titolo pagina e focus sul nuovo titolo quando cambia la vista (senza spostarlo a ogni aggiornamento automatico). Focus visibile, correzioni dei contrasti chiaro/scuro, colori di avvisi e privacy, placeholder leggibili, dimensioni tipografiche relative, pulsanti e righe adattabili al testo, supporto riduzione movimento e colori forzati. Nessuna modifica del database o dei calcoli.

## Verifiche eseguite

- 23 viste automatiche con axe-core: accesso, panoramica, gruppo, modifica spesa, impostazioni gruppo, notifiche/preferenze, statistiche/budget, import/export, strumenti, editor annidato e account anche con sezioni aperte. Nessuna violazione rilevata nei tag WCAG A/AA e best-practice analizzati.
- Larghezze 320, 390, 768 e 1280 CSS px, temi chiaro/scuro, testo al 200% su account e modulo spesa mobile: nessun overflow orizzontale della pagina nelle viste provate.
- Regressioni da tastiera: apertura con Invio, Tab ripetuto senza passare allo sfondo, Escape chiude soltanto la finestra superiore, focus ripristinato al comando di apertura.
- Chrome installato sul Mac, distinto dalla prova headless: accesso QA, navigazione, apertura popup da tastiera, albero accessibile con titolo/campi, Escape e ritorno del focus verificati.
- 11 test frontend superati e build riuscita. Strumenti esclusivamente di sviluppo; nessun dato reale usato.

## Ripetizione

Con Chrome installato, eseguire `npm ci` e poi `SGANCIA_A11Y_URL=http://localhost:18088 npm run test:a11y` nella cartella frontend. Usare esclusivamente un’istanza QA separata sulla porta loopback 18088: account sintetico `qa@example.org`, password `qa-password-long`, chiave `qa-installation-gate`, gruppo `Prova blocco 07` con due partecipanti e una spesa sintetica. Lo script rifiuta l’installazione normale sulla porta 8088. Fixture locale già predisposta in `.local/exchange-ui-qa/setup.py`; rigenerarla con credenziali QA, senza copiare dati reali. Report e screenshot sono esclusi da Git in `.local/accessibility-qa`. L’ambiente QA è stato spento al termine.

## Prove ancora aperte

Questi controlli non certificano la conformità completa e non sostituiscono l’uso reale con tecnologie assistive. Restano da provare VoiceOver su Mac, Safari e iPhone reale: accesso, navigazione per titoli/campi, errore di compilazione, creazione/modifica spesa, conferma rimborso, popup annidati, ingrandimento e orientamenti. Controllare anche l’annuncio degli aggiornamenti senza eccessive interruzioni. La relativa voce TODO resta aperta; nessuna prova su iPhone viene dichiarata eseguita.

Riferimenti di revisione: [dialoghi WAI APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [reflow W3C](https://www.w3.org/WAI/WCAG21/Understanding/reflow), [WCAG 2.1](https://www.w3.org/TR/WCAG21/).
