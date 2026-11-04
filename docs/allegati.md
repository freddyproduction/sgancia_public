# Allegati delle spese e ricevute dei rimborsi

Disponibili dal 3 novembre 2026. Nelle righe delle spese, la graffetta apre gli allegati; nella cronologia rimborsi, usare **Ricevute e allegati**. Selezionare uno o più file e confermare il caricamento. Immagini con anteprima e download; PDF con download, mai eseguiti come documenti attivi nell’origine dell’app.

## Formati e limiti

JPG, PNG, WebP e PDF non cifrati. Default: 10 MiB/file, 20 allegati attivi per spesa o rimborso e 100 MiB per account nel gruppo, compresi i file rimossi. La quota personale evita di rivelare l’occupazione di spese riservate di altre persone.

Configurazione in byte: `SGANCIA_ATTACHMENT_MAX_BYTES` (fino a 20 MiB), `SGANCIA_ATTACHMENT_GROUP_BYTES` (quota per account nel gruppo), `SGANCIA_ATTACHMENT_MAX_COUNT`. Non vengono mostrati contatori globali che includano file non autorizzati. Eventuali proxy devono consentire un corpo richiesta maggiore del limite; l’esempio Nginx è aggiornato a 12 MiB.

Le immagini vengono riconosciute dai dati effettivi, ricodificate senza metadati e ridimensionate fino a 4096px; oltre 40 milioni di pixel vengono rifiutate. Anteprima JPEG fino a 640px. I PDF devono avere 1–50 pagine, essere leggibili e privi delle strutture attive/non ammesse: JavaScript, avvii automatici, allegati incorporati, form attivi e collegamenti esterni. Un PDF rifiutato va esportato come documento semplice o caricato come immagine.

Il validatore opera in un processo separato con timeout di 9s e limite CPU; nel runtime Linux Docker è imposto anche un limite di memoria di 512 MiB. Questo non costituisce una certificazione antivirus. Validazione PDF con [pypdf 6.21.4](https://pypi.org/project/pypdf/6.21.4/), versione e hash bloccati.

## Permessi e conservazione

Pubblico ereditato dalla spesa/rimborso e ricontrollato ad ogni lista, anteprima e download; amministratori non aggirano gli ambiti riservati. I visualizzatori consultano soltanto. In gruppo congelato sono consentiti allegati dei rimborsi, non delle spese; archiviato in sola lettura.

La rimozione è reversibile dal cestino interno alla lista allegati. Eliminando una spesa, anche i suoi allegati diventano inaccessibili; ripristinandola tornano disponibili quelli non rimossi singolarmente. I file rimossi continuano a occupare spazio. Non c’è cancellazione fisica automatica; retention e pulizia amministrativa sono nel blocco 14. Non cancellare manualmente blob per fare spazio.

I file sono immutabili con chiavi opache in `data/attachments/`, montato su `/app/storage`; non sono cartella pubblica o URL statici. `storage-init` inizializza permessi privati per l’utente 10001 prima dell’API. Il collegamento registra la revisione della spesa al momento dell’upload; le successive modifiche economiche non cancellano il file.

## Ospiti

Allegati disabilitati per default nei link ospite. Il gestore può consentire esplicitamente gli allegati delle sole spese pubbliche, con nomi e dettagli abilitati perché il contenuto dei file potrebbe mostrarli. Ricevute e file riservati restano esclusi.

L’apertura della vista consuma un utilizzo e rilascia una concessione file firmata di massimo 5 minuti: i download non consumano nuove aperture, ma verificano ad ogni richiesta token, password, scadenza e revoca del link. Nessun token di accesso file negli URL. Il download si blocca subito se viene revocato il link o rimossa/nascosta la spesa.

## Backup

Il backup cifrato comprende DB, blob e anteprime con manifest/digest. È stato verificato un ripristino reale completo su dati sintetici dopo aver rimosso schema e file del solo ambiente QA. Vedi [backup e ripristino](backup-ripristino.md).
