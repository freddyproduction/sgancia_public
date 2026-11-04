# Chiave globale, passkey e compilazione automatica

La chiave globale apre il cancello dell’installazione. Il login personale, con password/MFA o passkey dell’account, resta un passaggio separato. L’amministratore globale conserva l’interruttore di attivazione del cancello; nessun cambio automatico alla sua configurazione.

## Passkey del cancello

Dopo l’accesso personale: Impostazioni → Conferma identità (se richiesta) → Passkey per la chiave globale → Aggiungi passkey installazione. Ogni utente attivo può registrare e rimuovere le proprie, al massimo 20. Sono credenziali distinte dalle passkey di login dell’account, con verifica dell’utente e requisito discoverable/resident. Il browser può proporre volto, impronta o PIN. Sul modulo iniziale usare “Apri con passkey installazione”, poi accedere al proprio account. Non viene creata una sessione personale dallo sblocco del cancello.

Richiedono l’indirizzo principale configurato, HTTPS oppure localhost e un browser compatibile. In LAN HTTP su IP continuare con la chiave testuale. Passkey su dominio e localhost sono legate a siti diversi: non vengono trasferite automaticamente. Non usare credenziali QA su un server nuovo.

Richieste casuali monouso da cinque minuti, verifica crittografica di origine/RP, presenza/verifica utente, contatore e limiti di tentativi. Gli endpoint iniziali non elencano account o ID di credenziali. Rimozione con conferma UI e identità recente; revoca anche degli accessi iniziali aperti con quella credenziale. Sospensione, cambiamenti della sicurezza dell’account o rotazione della chiave globale rendono inutilizzabili le passkey precedenti. Il recupero amministrativo delle passkey comprende quelle del cancello, escluso il superadmin come già previsto. Le credenziali non vengono eliminate automaticamente dal gestore del dispositivo.

Un ripristino elimina le passkey del cancello e le richieste pendenti, oltre a tutte le concessioni iniziali: registrarle nuovamente dopo avere usato la chiave testuale e verificato l’account. Questo evita di riattivare credenziali revocate dopo la data del backup. Non cambia la chiave globale originale e non attiva i link ospiti.

## Salvataggio della chiave testuale

Il modulo iniziale espone una voce distinta “Sgancia · accesso installazione”, username e password con autocomplete standard. Dopo verifica riuscita può proporre il salvataggio tramite l’API del gestore browser, se supportata; la casella permette di rinunciare. Il login personale usa invece la propria email e password. Nessuna copia della chiave viene salvata dall’app in localStorage, preferenze o database in chiaro.

Salvataggio e compilazione rimangono sotto il controllo del browser/gestore password (Password di Apple, browser o estensioni). Il sito non può imporre un salvataggio o garantire la proposta automatica su ogni dispositivo. In assenza dell’API specifica restano gli attributi standard per i gestori password; chiave manuale e passkey sono sempre percorsi separati. Una chiave salvata prima di una rotazione va aggiornata nel gestore.

Verificati backend con firme reali sintetiche e percorso browser completo con autenticatore virtuale residente. Biometria reale e proposta/autofill nel gestore password di Mac/iPhone ancora da confermare, insieme alle prove hardware del blocco 04.

Riferimenti: [passkey discoverable](https://developer.mozilla.org/en-US/docs/Web/Security/Authentication/Passkeys), [salvataggio credenziali nel browser](https://developer.mozilla.org/en-US/docs/Web/API/CredentialsContainer/store), [autocomplete dei moduli](https://developer.chrome.com/docs/modern-web-guidance/guides/forms/autofill-sign-in-form).
