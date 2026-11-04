# Durata della chiave installazione e del login

In **Admin globale → Amministrazione e operatività → Politiche di sicurezza e limiti** ci sono due controlli indipendenti:

- **Ricorda chiave dell’installazione:** quanto il browser conserva il cancello già sbloccato, con password globale o passkey di installazione.
- **Durata login utenti:** quanto resta valida la sessione personale, con password/MFA o passkey account.

Per ciascuno scegliere modalità browser oppure una quantità intera di minuti, ore, giorni, mesi o anni. Mese = 30 giorni, anno = 365 giorni; durata massima configurabile 100 anni. Le durate sono assolute dall’accesso, non si prolungano automaticamente a ogni richiesta. Le nuove impostazioni valgono per i prossimi accessi e non estendono quelli già emessi. Prima della personalizzazione rimangono i valori precedenti: chiave 1 giorno e login secondo session_hours dell’installazione.

## Logout e accessi successivi

Esci dall’account revoca e cancella sessione personale e cookie CSRF, ma conserva il cancello già verificato fino alla sua scadenza. La pagina di accesso controlla il cookie e mostra direttamente email/password, anche dopo ricaricamento. Non conserva la chiave in chiaro nell’app o nel localStorage: usa un token opaco HttpOnly, verificato sul server.

Se scade prima il login, basta rifare l’accesso personale. Se scade prima il cancello, serve la chiave (o la passkey installazione); se la sessione personale è ancora valida può essere ripresa senza chiedere nuovamente la password account. Sul modulo d’accesso **Dimentica la chiave dell’installazione** revoca il token di questo browser e cancella i cookie di accesso. Non cambia la chiave globale né gli altri dispositivi. L’eventuale salvataggio della chiave nel gestore password del browser è un’opzione distinta.

I cookie sono legati al browser/profilo e all’hostname: dominio, IP LAN e localhost non condividono automaticamente la concessione. Rotazione chiave, revoche, recupero e ripristino continuano a invalidare gli accessi secondo le regole esistenti. La conferma identità di cinque minuti per operazioni sensibili resta separata dalla durata del login.

## “Immediato”: fino alla chiusura del browser

Come concordato con il titolare, non significa scadenza di zero secondi, che renderebbe impossibile usare il sito. Vengono emessi cookie di sessione senza Max-Age/Expires persistenti; il server applica comunque un tetto di 30 giorni per i token di questa modalità. Il browser decide la fine della propria sessione: chiudere una sola scheda non basta e il ripristino delle sessioni del browser può conservarli. Per una revoca certa usare Esci e, se necessario, Dimentica la chiave.

Anche le durate persistenti possono essere accorciate o cancellate dalle regole del browser: selezionare anni non garantisce che il browser conservi il cookie per tutto il periodo. Il server non accetta mai un token oltre la scadenza registrata. Riferimento: [documentazione browser Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).

## Configurazione e compatibilità

Le opzioni sono conservate nel runtime_policy dell’installazione e incluse nei backup, senza nuova migrazione. session_duration e gate_duration hanno unit/value; session_duration assente mantiene la compatibilità con session_hours. Il frontend mostra i due controlli separati; il vecchio limite di 168 ore non vincola le nuove durate esplicite. Non modificare `.env` o rigenerare chiavi per impostare questi tempi.
