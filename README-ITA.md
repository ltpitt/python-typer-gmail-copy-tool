# python-typer-gmail-copy-tool

Uno strumento da riga di comando (CLI) costruito con [Typer](https://typer.tiangolo.com/) che consente di analizzare, copiare, confrontare e ripulire le email tra account Gmail. Progettato per essere affidabile, riprendere automaticamente in caso di interruzioni e garantire l'integrità dei dati.

---

## 📌 Funzionalità

- Analizza il numero totale di email in un account Gmail
- Copia tutte le email (inclusi allegati e metadati) da un account Gmail a un altro
- Riprende automaticamente le operazioni di copia interrotte
- Confronta gli account sorgente e destinazione per verificare il successo della copia
- Elimina le email dall’account sorgente che sono già presenti nell’account di destinazione
- Interfaccia CLI modulare con comandi chiari

---

## 🚀 Installazione

### Per Utenti Normali

Per installare lo strumento come utente normale, esegui:

```bash
pip install .
```

Questo installerà lo strumento e le sue dipendenze nel tuo ambiente.

### Per Sviluppatori

Per installare lo strumento in modalità modificabile per lo sviluppo, esegui:

```bash
pip install -e .
```

Questo ti permetterà di apportare modifiche al codice sorgente e testarle immediatamente senza reinstallare il pacchetto.

---

1. Abilitare l’API Gmail nella Google Cloud Console.
2. Creare credenziali OAuth 2.0.
3. Scaricare `credentials.json` e posizionarlo nella directory di lavoro.

### Come ottenere il file `credentials.json` per l’accesso all’API Gmail

1. Vai su [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un nuovo progetto (o seleziona uno esistente).
3. Vai su **API e servizi > Libreria** e abilita **Gmail API**.
4. Vai su **API e servizi > Credenziali**.
5. Clicca su **Crea credenziali** > **ID client OAuth**.
   - Se richiesto, configura prima la schermata di consenso OAuth.
   - Scegli **Applicazione desktop** come tipo di applicazione.
   - Dai un nome (es. "gmail-copy-tool").
6. Clicca **Crea**. Scarica il file `credentials.json`.
7. Posiziona `credentials.json` nella directory di lavoro del progetto (dove esegui la CLI).

Questo file consente all’app di richiedere l’autorizzazione dell’utente per accedere a Gmail.

---

## 🛠️ Configurazione

Lo strumento utilizza OAuth 2.0 per accedere a Gmail. Al primo avvio, richiederà l’autorizzazione e salverà i token localmente.

- `credentials.json`: credenziali OAuth del client
- `token_source.json`: token per l’account sorgente
- `token_target.json`: token per l’account di destinazione
- `.gmail-copy-checkpoint.json`: memorizza l’ID dell’ultimo messaggio copiato per riprendere la copia

---

## 📚 Utilizzo

Esegui qualsiasi comando con `--help` per vedere le opzioni disponibili:
```bash
gmail-copy-tool --help
```

---

## 🧪 Comandi CLI

### `analyze`

```bash
gmail-copy-tool analyze --account source@gmail.com --token-file token_source.json
```

Conta il numero totale di email nell’account Gmail specificato. Usa file token esplicito per sicurezza.

---

### `copy`

```bash
gmail-copy-tool copy --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Copia tutte le email dall’account sorgente a quello di destinazione.

- Include allegati, etichette e metadati
- Riprende automaticamente in caso di interruzione
- Salta i messaggi già copiati utilizzando il tracciamento degli ID
- Usa file token espliciti per sicurezza e ripetibilità

---

### `compare`

```bash
gmail-copy-tool compare --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Confronta gli account sorgente e destinazione per verificare che tutte le email siano state copiate correttamente.

- Utilizza hash canonici per confronto robusto (ignora header aggiunti da Gmail)
- Riporta eventuali messaggi mancanti o non corrispondenti

---

### `remove-copied`

```bash
gmail-copy-tool remove-copied --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Rimuove dall’account sorgente tutte le email che sono presenti nell’account di destinazione (confronto tramite hash canonico).

- Operazione sicura: elimina solo le email confermate nel target
- Solo le email effettivamente copiate vengono eliminate; le email extra rimangono
- Utile per la pulizia dopo la migrazione per evitare duplicati nel sorgente

---

## 🧾 Esempio di Configurazione Test

Un file di esempio (`tests/test_config_example.json`) è fornito per aiutare gli utenti a eseguire test di integrazione e automatizzare i comandi CLI.

**Campi:**
- `source_account`: indirizzo Gmail sorgente
- `target_account`: indirizzo Gmail destinazione
- `source_token`: file token OAuth per la sorgente
- `target_token`: file token OAuth per la destinazione
- `source_credentials`: file credenziali per la sorgente
- `target_credentials`: file credenziali per la destinazione
- `label`: (opzionale) etichetta Gmail da filtrare
- `after`: (opzionale) solo email dopo questa data (YYYY-MM-DD)
- `before`: (opzionale) solo email prima di questa data (YYYY-MM-DD)

**Utilizzo:**
- Modifica i campi in base ai tuoi account Gmail e file token/credenziali.
- Dopo la modifica, rinomina il file in `tests/test_config.json` per eseguire i test di integrazione. Il runner dei test userà solo `test_config.json`.

```json
{
  "source_account": "source@gmail.com",
  "target_account": "target@gmail.com",
  "source_token": "token_source.json",
  "target_token": "token_target.json",
  "source_credentials": "credentials_source.json",
  "target_credentials": "credentials_target.json",
  "label": null,
  "after": null,
  "before": null
}
```

I test di integrazione in `tests/test_integration.py` verificano in modo robusto tutti i principali comandi CLI:

- **Setup:** Sia la mailbox sorgente che quella di destinazione vengono azzerate e popolate con email note prima di ogni test.
- **Assert:** Tutti i controlli di integrità usano hash canonici, ignorando header aggiunti da Gmail per affidabilità.
- **Copertura:**
  - `copy`: Verifica che tutte le email siano copiate, con hash corrispondenti tra sorgente e destinazione.
  - `compare`: Verifica che gli hash tra sorgente e destinazione corrispondano dopo la migrazione.
  - `remove-copied`: Verifica che solo le email copiate vengano eliminate dalla sorgente, le email extra rimangono.
  - `delete-duplicates`: Verifica che solo i veri duplicati vengano eliminati, tramite matching hash.

---

## 🧠 Dettagli Comportamentali

- **Meccanismo di Ripresa**: Memorizza l’ID dell’ultimo messaggio copiato in `.gmail-copy-checkpoint.json`. Al riavvio, riprende da quel punto.
- **Logica di Confronto**: Utilizza hash canonici (ignorando header aggiunti da Gmail) per verifica robusta dell’integrità e deduplicazione.
- **Dati Copiati:**
  - Corpo dell’email
  - Allegati
  - Etichette
  - Metadati delle conversazioni
- **Dati Esclusi:**
  - Cartella Spam
  - Cestino
  - Bozze

---

## ⚙️ Variabili d'Ambiente

- `GMAIL_COPY_TOOL_DEBUG=1`: Abilita la modalità debug per log dettagliati utili allo sviluppo e troubleshooting.

---

## 🛠️ Risoluzione dei Problemi

- Se vedi richieste di autenticazione, verifica che i file token siano presenti e validi.
- Per errori di indentazione o import, controlla che non ci siano blocchi di codice duplicati o in conflitto nei file sorgente.
- Per log troppo verbosi, imposta `GMAIL_COPY_TOOL_DEBUG=0` (default) per uso in produzione.

---

## ⚠️ Limitazioni API Gmail & Note di Affidabilità

Questo strumento è progettato per funzionare in modo affidabile con l’API Gmail, ma ci sono alcune limitazioni e particolarità da considerare:

- **Confronto Messaggi:** Gmail può aggiungere header, modificare la struttura MIME o cambiare gli ID dei messaggi durante la migrazione. Il confronto diretto per ID o contenuto grezzo non è affidabile. Questo tool usa hash canonici (ignorando header aggiunti e campi non essenziali) per verificare l’integrità tra account.
- **Consistenza API:** Le operazioni API (copia, eliminazione, etichette) potrebbero non essere immediatamente visibili. I test di integrazione usano attese esplicite (sleep) dopo queste operazioni per garantire che le modifiche siano effettivamente visibili prima della verifica. Questo è essenziale per test e migrazioni affidabili.
- **Rate Limit & Quote:** L’API Gmail impone limiti di velocità. Il tool implementa backoff esponenziale e retry per invio e modifica dei messaggi. Se si raggiungono i limiti, il tool attende e riprova automaticamente; le migrazioni grandi richiedono pazienza.
- **Errori Parziali:** L’API Gmail può fallire o restituire errori transitori. Tutte le operazioni sono progettate per essere ripetibili e idempotenti. Se interrotte, puoi rilanciare i comandi in sicurezza: solo i messaggi mancanti o non processati verranno gestiti.
- **Etichette & Metadati:** Gmail può ritardare l’applicazione di etichette o modifiche ai metadati. Test e logica di migrazione includono attese esplicite e controlli ripetuti per confermare le modifiche.
- **Token & Permessi:** Se i token scadono o cambiano i permessi, è necessaria una nuova autenticazione. Il tool chiederà l’autorizzazione quando serve.

**Best Practice:**
- Usa sempre file token/config espliciti per sicurezza e ripetibilità.
- Aspettati ritardi e sii paziente con inbox grandi o operazioni bulk.
- Usa il confronto hash canonico per vera integrità dei dati.
- Controlla i log per warning/errori e riprova se necessario.

---

## 🧪 Note di Sviluppo

- Costruito con [Typer](https://typer.tiangolo.com/) per una CLI intuitiva
- Utilizza `google-api-python-client` per accedere a Gmail
- Struttura modulare per facilitare estensioni future
- Logging professionale: solo warning/errori per gli utenti, debug/info solo in modalità debug
- Tutti i comandi CLI accettano opzioni esplicite per i file token per sicurezza e ripetibilità
- Tutti i test di integrazione verificano l’integrità dei dati tramite hash canonici

---

## 🧩 Miglioramenti Futuri

- Aggiunta di filtri (per etichetta, data, mittente)
- Supporto per modalità simulazione (dry-run)
- Aggiunta di concorrenza per inbox molto grandi
- Esportazione di log e report

---

## 🧑‍💻 Contributi

Contributi benvenuti. Assicurati che il codice sia tipizzato e testato.

---

## 📄 Licenza

Licenza MIT
