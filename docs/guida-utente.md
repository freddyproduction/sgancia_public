# Guida utente di Sgancia

Generata dalla stessa fonte della guida nell’app: `frontend/src/help-content.json`.

## Accesso, email e recupero

Apri l’indirizzo indicato dall’amministratore. Se il cancello d’installazione è attivo, inserisci la chiave o usa la passkey dell’installazione; poi accedi al tuo account con password e, se richiesta, MFA, oppure con una passkey personale. Le due passkey hanno scopi distinti.

Registrazioni libere, con approvazione, su invito o chiuse dipendono dalla policy globale. Per verificare l’email richiedi il messaggio in Impostazioni account: SMTP deve essere configurato dall’amministratore. Un link di verifica o recupero scade e si usa una sola volta. Non condividere password, codici MFA, inviti o chiavi.

Se perdi i fattori usa un codice di recupero conservato privatamente. Un admin globale può recuperare i fattori degli altri utenti, esclusi i superadmin. Non esistono password universali.

La chiave dell’installazione e il login hanno durate separate, configurabili dall’admin globale. Esci revoca l’account ma conserva la chiave già verificata; al ritorno trovi direttamente il login finché il cancello è valido. Per cancellarlo usa Dimentica la chiave dell’installazione nel modulo di accesso. La modalità Immediato usa cookie fino alla chiusura del browser, con limite server di 30 giorni; il ripristino delle sessioni del browser può conservarli. Le durate si applicano ai nuovi accessi e sono distinte dalla conferma identità delle operazioni sensibili.

Puoi ricevere un link di invito condiviso alla piattaforma: permette più registrazioni entro scadenza e limite di utilizzi. Non è un invito a un gruppo e non cambia il ruolo di un account esistente. Se è prevista approvazione devi attendere la conferma.

## Account, aspetto e metodi di pagamento

In Impostazioni modifica nome, email e password, gestisci MFA, passkey e sessioni. Le operazioni sensibili richiedono Conferma identità recente: quando necessario si apre un popup per password account e codice MFA/recupero se attivo. Dopo la verifica torna al modulo e premi di nuovo il pulsante dell’operazione; non viene ripetuta automaticamente. Il tema chiaro o scuro è salvato sull’account e si applica anche agli altri dispositivi.

I nuovi account iniziano con il tema scuro; puoi cambiarlo in Aspetto. Le preferenze degli account esistenti restano invariate. In Il mio account puoi scegliere una foto o un’icona che ti segue nel saluto, nel menu e nei membri dei tuoi gruppi. Per foto account, gruppi e metodi di pagamento si apre un’anteprima: oltre 2 MB viene chiesto di comprimere, scegli adattamento automatico o ritaglio quadrato con zoom e posizione; poi salva il modulo. L’originale resta invariato. Aggiungi i tuoi metodi di pagamento con descrizione, dati utili e immagine nei limiti indicati. Sono recapiti per ricevere denaro: Sgancia non conserva carte per addebiti e non effettua pagamenti. Controlla destinatario e importo prima di usare servizi esterni.

## Gruppi, ruoli e inviti

Crea un gruppo con nome e valuta principale. Impostazioni gruppo raccoglie descrizione, icona o immagine, membri, ruoli, stato, inviti e cestino. Il proprietario ha tutti i poteri degli admin. Gli admin rimuovono membri e visualizzatori, riaprono gruppi archiviati e ripristinano gruppi eliminati. Il proprietario deve cedere la proprietà a un account reale prima di uscire se ne esistono altri attivi; se restano solo virtuali può uscire e il gruppo passa nel cestino, conservando i dati e restando ripristinabile. Proprietario e amministratori di gruppo gestiscono il gruppo; i membri modificano le spese visibili; il visualizzatore consulta soltanto. Essere admin globale non rende visibili tutte le spese riservate.

Puoi aggiungere partecipanti senza account. Per associare un account successivamente usa l’invito o l’associazione esplicita della persona esistente: non creare un duplicato e non associare soltanto in base al nome. L’anteprima mostra chi verrà collegato e i conti conservati.

I link per nuovi account, i codici per account già registrati e i link ospite sono percorsi distinti. I link ospite sono in sola lettura e solo pubblici; inizialmente sono disabilitati globalmente. Se abilitati possono avere password, scadenza e limite di aperture. Condividili privatamente.

Ogni gruppo ha codici e link diretti riutilizzabili per membro, visualizzatore e admin in Impostazioni gruppo → Inviti e ospiti / Codici invito. Gli admin vedono tutti i codici e possono rigenerarli; i membri vedono membro e visualizzatore. Ogni codice permette di collegare soltanto virtuali dello stesso ruolo. Aprendo il link trovi il codice già inserito anche dopo il login. Copia il link dal dominio pubblico se devi condividerlo fuori dalla LAN. Da Ho un invito puoi entrare come nuova persona oppure collegare la tua persona senza account conservando spese e saldi, e scegliere il nome nel gruppo. Condividi privatamente i codici: permettono di collegare i virtuali e non autorizzano la registrazione alla piattaforma.

## Inserire e modificare una spesa

Premi Aggiungi spesa, compila titolo, data, categoria e note. Aggiungi una o più voci. Per ogni voce la casella accanto al nome indica chi divide il costo, la stella chi ha anticipato. Più pagatori possono indicare anticipi precisi o dividere automaticamente il resto. Puoi creare categorie del gruppo.

Sono disponibili parti uguali, percentuali, importi esatti, pesi e quantità. Nei campi importo puoi usare 12,50 + 8,90 oppure 100 * (1 - 20%). Controlla sempre l’anteprima: la somma dei pagatori e delle quote deve coincidere con il totale.

Esempio sintetico: Anna anticipa 60 EUR per Anna, Luca e Bea in parti uguali. Ogni quota è 20 EUR; ad Anna devono tornare 40 EUR. I resti al centesimo sono distribuiti in modo deterministico.

Usa la matita per modificare, il cestino per eliminare. Nel modulo puoi togliere una voce; eliminando l’ultima si elimina l’intera spesa. La cronologia conserva le revisioni. Se qualcuno ha cambiato la stessa spesa, ricarica la versione corrente prima di confermare.

Su mobile le azioni di ogni spesa sono raggruppate con nomi visibili: Cronologia, Allegati, Modello, Duplica, Modifica ed Elimina; Visibilità compare per le spese riservate modificabili. Su computer passa il mouse sulle icone per leggere le descrizioni. Il pulsante ? accanto a Le spese apre la spiegazione di tutte le azioni, anche da telefono o tastiera, senza eseguirle.

## Spese riservate e rivelazione

Per un regalo o altra spesa riservata scegli il pubblico autorizzato. Autore, pagatori e partecipanti alle quote devono essere inclusi. Gli esclusi non vedono la spesa né indizi nei saldi, report o notifiche. I gestori del gruppo non possono superare questo pubblico.

Puoi programmare o eseguire una rivelazione secondo i permessi. In presenza di incassi riservati confermati usa l’anteprima di riconciliazione e il consenso esplicito: non si possono semplicemente spostare debiti già pagati tra pubblici diversi. Dopo un ripristino le rivelazioni programmate restano sospese per controllo.

Sgancia applica la privacy nel software: non offre cifratura end-to-end tra utenti e amministratore del server.

## Valute e conversione

La valuta principale si gestisce nelle impostazioni del gruppo. Per una spesa in valuta diversa scegli la valuta originale e, se desiderato, il cambio automatico: la quotazione disponibile viene applicata all’inserimento e conservata con la spesa. Non è un cambio in tempo reale garantito né una transazione bancaria. Se il servizio non è disponibile puoi usare un tasso manuale.

Il cambio della valuta principale richiede anteprima e conferma perché converte i conti esistenti e conserva lo storico. In panoramica valute diverse restano separate: non si sommano EUR e USD senza una conversione esplicita.

## Anticipi, debiti e algoritmo Smart

Spese del gruppo comprende tutte le spese visibili al tuo account, incluse le riservate autorizzate. Hai anticipato è quanto hai pagato. Ti devono tornare e Devi restituire indicano importi ancora aperti: non coincidono necessariamente con il saldo netto.

Clicca Ti devono tornare per vedere chi deve pagarti e confermare quanto hai davvero ricevuto. Clicca Devi restituire per vedere i destinatari. La panoramica aggrega i gruppi riconoscendo l’account; gli omonimi senza account restano distinti. Una conferma aggregata viene ripartita nei gruppi dal software con controllo degli importi correnti.

Smart è attivo di default per gruppo e riduce i passaggi di pagamento nei limiti della visibilità. Puoi disattivarlo nelle impostazioni del gruppo. Non cambia le quote dovute e non trasferisce denaro. Ambiti riservati diversi restano protetti.

## Saldato, rimborsi e contestazioni

Saldato conferma denaro effettivamente ricevuto. Per un membro ordinario può premerlo soltanto il ricevente, non chi deve dare soldi. Il debitore può registrare una segnalazione in attesa: i conti cambiano quando il ricevente conferma. Per persone senza account valgono le deleghe e le regole dei gestori.

In Rimborsi consulta lo stato, conferma o contesta con motivazione. Ripristina rimborso annulla la conferma e riapre il debito conservando lo storico; non restituisce denaro sul conto bancario. Eliminare una spesa non cancella un trasferimento già registrato.

Una contestazione della spesa si consulta nello storico; le revisioni precedenti restano disponibili alle persone autorizzate.

## Scontrini, immagini e cestino

Allega foto o documenti alla spesa o al pagamento autorizzato. Formati e limiti sono indicati dal software e configurabili dall’admin. Le immagini vengono normalizzate e i file sono serviti con verifica dei permessi; non sono URL pubblici permanenti.

Puoi ripristinare spese e gruppi dal rispettivo cestino secondo il tuo ruolo. I gruppi archiviati sono nascosti per impostazione predefinita: usa l’icona archivio vicino a I tuoi gruppi per mostrarli. Il cestino non equivale alla cancellazione fisica dei backup.

## Modelli, ricorrenze, ricerca e report

Duplica una spesa o crea un modello per riutilizzare le voci. Le ricorrenze richiedono configurazione e conferma esplicita; dopo un ripristino vengono sospese. Gli anticipi sono pagamenti distinti con regole proprie: controlla sempre l’anteprima.

Ricerca, statistiche e conti offre filtri, grafici, budget, simulazioni e chiusura del gruppo. Una simulazione non registra pagamenti. Importa/esporta supporta CSV e JSON e report PDF nei limiti del tuo pubblico. Prima dell’importazione controlla associazioni, quote e provenienza per evitare duplicati.

## Notifiche e aggiornamento automatico

Apri la campanella in panoramica o Notifiche nel menu: lo stesso centro è disponibile da Impostazioni → Notifiche → Mostra notifiche. In arrivo, Da leggere, Archivio e Cestino permettono lettura, archiviazione e ripristino personali; le preferenze restano nelle impostazioni. Il centro notifiche mostra solo eventi autorizzati; archivio e cestino rispettano la durata di conservazione. Imposta frequenza, fuso orario, durata e soglie per account o gruppo. Email e Telegram sono facoltativi; l’email richiede indirizzo verificato e SMTP configurato. I messaggi esterni sono generici e rimandano ai dati protetti nel software.

L’app aggiorna dopo una modifica e gli altri client si riallineano circa ogni due secondi quando la pagina è visibile. I moduli già modificati non vengono sovrascritti. Se la rete manca, verifica lo stato prima di riprovare: un errore di collegamento non significa che la modifica non sia stata salvata.

## Telegram dal tuo account

L’admin abilita Telegram nelle impostazioni globali e salva; non occorre usare il terminale. Apri il bot dalla Panoramica, invia /id, inserisci quell’ID nelle impostazioni account e genera un collegamento monouso valido cinque minuti. Solo il tuo ID può completarlo in chat privata.

Riservate e notifiche richiedono consensi separati, inizialmente spenti. Usa /gruppi, /saldi, /spesa, /spese, /cestino, /foto, /rimborsi e /notifiche. Il wizard propone un’anteprima da confermare. Puoi scollegarti dal web o con /scollega; i comandi avanzati rimandano al web.

Non inviare mai chiave globale, password o codici MFA al bot. Telegram è un servizio esterno che riceve i dati autorizzati. L’OCR delle foto non è ancora disponibile.

## Amministratori e recupero dell’installazione

L’admin globale gestisce registrazioni, ruoli globali, SMTP, chiave d’accesso, politiche, Telegram, link ospiti, audit e backup. L’admin del gruppo gestisce soltanto il proprio gruppo. Il primo account del bootstrap è superadmin. Un altro superadmin può assegnare o revocare questo ruolo, senza cancellare l’account; l’ultimo è protetto. Il nome non determina i privilegi.

I backup automatici e i link ospiti sono inizialmente spenti; le notifiche esterne e Telegram richiedono configurazione. Custodisci le chiavi di cifratura e recupero separatamente dal server. Un backup cifrato senza le chiavi originali non è recuperabile.

Il ripristino revoca sessioni, inviti e collegamenti sensibili e sospende automatismi: prima di riabilitarli controlla utenti, saldi e pianificazioni. Per aggiornamenti e recupero seguire le guide operative della versione installata.

In Registrazioni e inviti globali scegli la modalità corrente e gestisci le richieste in attesa: Approva attiva l’account, Rifiuta lo sospende senza cancellarlo. Gli inviti globali hanno durata da 1 a 90 giorni, stato e filtri. Rinnova conserva il codice; Rigenera ne crea uno nuovo e revoca il precedente; Rimuovi / revoca lo invalida conservando lo storico. Il link si copia solo alla creazione o rigenerazione e non viene inviato automaticamente. Gli inviti account + gruppo restano nel gruppo.

Solo i superadmin assegnano ruoli globali e scelgono i permessi degli admin: account, registrazioni, SMTP, accesso, politiche, ospiti, Telegram, backup, audit e sessioni. I nuovi admin partono senza permessi aggiuntivi. Negli inviti si può proporre il ruolo; in modalità approvazione rimane senza effetto finché un superadmin non conferma la richiesta. Le nomine privilegiate richiedono password e MFA se attiva. La revoca del ruolo non elimina account o conti.

Gli inviti condivisi si creano in Amministrazione → Registrazioni e inviti globali: durata, quota, rinnovo, revoca e rigenerazione manuale o automatica. I superadmin possono sospendere, riattivare ed eliminare account a ogni livello con password e MFA; l’ultimo superadmin attivo e il proprio account sono protetti. Eliminare anonimizza il profilo e conserva le spese condivise, con trasferimento delle proprietà o gruppi nel cestino.

## Disponibile, da abilitare e in arrivo

Disponibile: account e sicurezza, gruppi e ruoli, spese composte/riservate, valute, saldi Smart, rimborsi, allegati, storico, import/export, statistiche, notifiche e bot Telegram.

Da abilitare o configurare: Telegram, SMTP e verifica email, email di notifica, backup automatici e prove di recupero, link ospiti, ricorrenze e rivelazioni. Alcune opzioni spettano all’admin globale; altre all’autore o ai gestori del gruppo.

In arrivo: PWA/offline completa, OCR locale e ulteriori miglioramenti della roadmap. Restano prove reali di passkey su Mac/iPhone, SMTP e Telegram, server Linux, HTTPS/proxy e CI remota. La versione corrente è di sviluppo, non una dichiarazione di prima release stabile.

Nuove richieste future: backup portabile completo, backup selettivi dei gruppi e personalizzazione; rafforzamento della sicurezza con prove di attacco isolate; studio di cifratura end-to-end (oggi non disponibile); accesso Google/GitHub aggiuntivo senza rimuovere gli account Sgancia. Gestione multipla dei superadmin, ruoli negli inviti/approvazioni e permessi degli admin globali sono disponibili nella gestione globale. La roadmap distingue le funzioni pianificate da quelle realmente disponibili.
