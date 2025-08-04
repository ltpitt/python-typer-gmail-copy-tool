# python-typer-gmail-copy-tool

Questo strumento da riga di comando (CLI), scritto in Python, permette di copiare le email da un account Gmail a un altro e verifica automaticamente il risultato della copia.

È possibile eseguire il comando con l’opzione `--help` per capire come funziona.

Lo strumento è costruito utilizzando Python Typer.

È possibile eseguire un’analisi su un account Gmail di destinazione per capire quante email sono presenti in totale.

È anche possibile copiare tutte le email da un account Gmail sorgente a uno di destinazione.

La copia garantisce che tutte le email e gli altri dati (allegati, ecc.) vengano trasferiti correttamente dall’account sorgente a quello di destinazione.

Il meccanismo di copia è in grado di riprendere in modo intelligente: se una copia viene interrotta, può continuare automaticamente dal punto di interruzione, evitando di ricopiare tutto da capo.

Lo strumento, al termine della copia, è in grado di eseguire un confronto per confermare che tutte le email presenti nell’account sorgente siano anche presenti nell’account di destinazione.

È anche possibile eseguire il confronto in modo indipendente, come funzione specifica dello strumento (ad esempio, confrontare solo un account Gmail sorgente con uno di destinazione).

Lo strumento include inoltre una funzionalità che consente di eliminare dall’account Gmail sorgente tutte le email che sono già presenti nell’account di destinazione.








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

```bash
pip install typer google-api-python-client oauth2client

1. Abilitare l’API Gmail nella Google Cloud Console.
2. Creare credenziali OAuth 2.0.

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
gmail-copy-tool analyze --account source@gmail.com
```

Conta il numero totale di email nell’account Gmail specificato.

---

### `copy`

```bash
gmail-copy-tool copy --source source@gmail.com --target target@gmail.com
```

Copia tutte le email dall’account sorgente a quello di destinazione.

- Include allegati, etichette e metadati
- Riprende automaticamente in caso di interruzione
- Salta i messaggi già copiati utilizzando il tracciamento degli ID

---

### `compare`

```bash
gmail-copy-tool compare --source source@gmail.com --target target@gmail.com
```

Confronta gli account sorgente e destinazione per verificare che tutte le email siano state copiate correttamente.

- Utilizza gli ID dei messaggi Gmail per il confronto
- Riporta eventuali messaggi mancanti o non corrispondenti

---

### `delete-duplicates`

```bash
gmail-copy-tool delete-duplicates --source source@gmail.com --target target@gmail.com
```

Elimina le email dall’account sorgente che sono già presenti nell’account di destinazione.

- Operazione sicura: elimina solo corrispondenze esatte
- Utile per la pulizia dopo la migrazione

---

## 🧠 Dettagli Comportamentali

- **Meccanismo di Ripresa**: Memorizza l’ID dell’ultimo messaggio copiato in `.gmail-copy-checkpoint.json`. Al riavvio, riprende da quel punto.
- **Logica di Confronto**: Utilizza gli ID dei messaggi Gmail per rilevare duplicati e verificare l’integrità.
- **Dati Copiati**:
  - Corpo dell’email
  - Allegati
  - Etichette
  - Metadati delle conversazioni
- **Dati Esclusi**:
  - Cartella Spam
  - Cestino
  - Bozze

---

## 🧪 Note di Sviluppo

- Costruito con [Typer](https://typer.tiangolo.com/) per una CLI intuitiva
- Utilizza `google-api-python-client` per accedere a Gmail
- Struttura modulare per facilitare estensioni future

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
