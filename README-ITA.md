# Gmail Copy Tool

Strumento da riga di comando semplice e potente per gestire account Gmail: copiare email, verificare trasferimenti e pulire duplicati.

---

## ✨ Guida Rapida (Passo-Passo per Principianti)

### 1. Scarica e Apri il Progetto

1. Scarica o clona questo progetto sul tuo computer
2. Apri un terminale/prompt dei comandi
3. Vai alla cartella del progetto:
   ```bash
   cd percorso\a\python-typer-gmail-copy-tool
   ```

### 2. Crea e Attiva l'Ambiente Virtuale

**Su Windows:**
```bash
# Crea l'ambiente virtuale (solo la prima volta)
python -m venv .venv

# Attivalo (fai questo ogni volta che apri un nuovo terminale)
.venv\Scripts\activate
```

**Su Mac/Linux:**
```bash
# Crea l'ambiente virtuale (solo la prima volta)
python3 -m venv .venv

# Attivalo (fai questo ogni volta che apri un nuovo terminale)
source .venv/bin/activate
```

Saprai che è attivo quando vedi `(.venv)` all'inizio della riga del terminale.

### 3. Installa lo Strumento

```bash
pip install -e .
```

Questo installa il comando `gmail-copy-tool`.

### 4. Configura i Tuoi Account

Prima di usare lo strumento, devi ottenere le credenziali OAuth da Google Cloud Console (vedi sezione sotto).

Poi usa il wizard interattivo:

```bash
gmail-copy-tool setup
```

Il wizard ti guiderà attraverso:
- Creazione delle credenziali OAuth nella Google Cloud Console
- Autenticazione con i tuoi account Gmail
- Salvataggio degli account con nickname facili da ricordare (es. "vecchio", "nuovo")

### 5. Inizia ad Usarlo!

```bash
# Sincronizza tutte le email da un account all'altro (interattivo)
gmail-copy-tool sync vecchio nuovo

# Sincronizza solo email del 2024
gmail-copy-tool sync vecchio nuovo --year 2024

# Sincronizzazione completamente automatica (nessuna domanda)
gmail-copy-tool sync vecchio nuovo --yes

# Vedi i tuoi account configurati
gmail-copy-tool list
```

**Ricorda:** Attiva sempre l'ambiente virtuale prima! Se vedi "comando non trovato", esegui `.venv\Scripts\activate` (Windows) o `source .venv/bin/activate` (Mac/Linux).

---

## 🔐 Ottenere le Credenziali OAuth

Prima di usare questo strumento, devi creare le credenziali OAuth nella Google Cloud Console:

1. Vai alla [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto (o selezionane uno esistente)
3. Abilita l'**API Gmail**:
   - Vai su **APIs & Services > Library**
   - Cerca "Gmail API" e clicca **Enable**
4. Crea le credenziali OAuth:
   - Vai su **APIs & Services > Credentials**
   - Clicca **Create Credentials > OAuth client ID**
   - Configura la schermata di consenso se richiesto
   - Scegli **Desktop app** come tipo di applicazione
   - Scarica il file JSON delle credenziali
5. Quando esegui `gmail-copy-tool setup`, fornisci il percorso a questo file di credenziali

Il wizard di setup ti guiderà nel resto!

---

## 📌 Funzionalità

- **Facile per Principianti**: Istruzioni chiare passo-passo, nessun comando complesso
- **Setup Semplice**: Il wizard interattivo ti guida attraverso la configurazione OAuth
- **Comandi Facili**: Usa nickname degli account invece di indirizzi email e percorsi file
- **Rinnovo Token Automatico**: Gestisce automaticamente i token scaduti/revocati
- **Sincronizzazione Interattiva**: Confronta, copia email mancanti e pulisci quelle extra in un solo comando
- **Rimozione Automatica Duplicati**: Trova e rimuove email duplicate dall'account di destinazione
- **Modalità Non-Interattiva**: Usa il flag `--yes` per sincronizzazione completamente automatica
- **Barre di Progresso Visive**: Bellissimi indicatori di progresso in tempo reale
- **Scorciatoie Anno**: Filtra rapidamente per anno con `--year 2024`
- **Confronto Basato sul Contenuto**: Usa un'impronta digitale (subject+from+date+allegati) per rilevare differenze
- **Elaborazione Batch**: Gestisce migliaia di email efficientemente con limite di velocità intelligente

---

## 📚 Comandi

### Wizard di Setup
```bash
gmail-copy-tool setup
```
Wizard interattivo per aggiungere account Gmail. Ti serviranno:
- File JSON delle credenziali OAuth (vedi sopra)
- Accesso all'account Gmail per autorizzare

### Elenca Account
```bash
gmail-copy-tool list
```
Mostra tutti gli account configurati con i loro nickname e indirizzi email.

### Sincronizza Email
```bash
gmail-copy-tool sync ORIGINE DESTINAZIONE [OPZIONI]
```

Sincronizza le email dall'account ORIGINE all'account DESTINAZIONE. Il comando:
- Confronta entrambi gli account usando un'impronta basata sul contenuto (subject + from + date + allegati)
- Mostra il conteggio delle email totali vs uniche (rileva duplicati)
- Copia le email mancanti nella DESTINAZIONE
- Chiede interattivamente se vuoi eliminare le email extra dalla DESTINAZIONE (o elimina automaticamente con `--yes`)
- **Rimuove automaticamente le email duplicate dalla DESTINAZIONE** (mantiene la copia più vecchia)
- Mostra bellissime barre di progresso in tempo reale per tutte le operazioni
- Visualizza un riepilogo dettagliato dei tempi di esecuzione

Esempi:
```bash
# Sincronizza tutto
gmail-copy-tool sync vecchio nuovo

# Sincronizza solo email del 2024
gmail-copy-tool sync vecchio nuovo --year 2024

# Sincronizza email in un intervallo di date
gmail-copy-tool sync vecchio nuovo --after 2024-01-01 --before 2024-06-30

# Sincronizza email con una label specifica
gmail-copy-tool sync vecchio nuovo --label "Importante"

# Mostra solo le prime 10 differenze (nessuna modifica)
gmail-copy-tool sync vecchio nuovo --limit 10

# Sincronizzazione completamente automatica (nessuna domanda, conferma tutto)
gmail-copy-tool sync vecchio nuovo --yes
```

**Opzioni:**
- `--yes` / `-y` - Auto-conferma tutte le domande (modalità non-interattiva per automazione)
- `--year ANNO` - Sincronizza solo email di un anno specifico
- `--after DATA` - Sincronizza email dopo questa data (YYYY-MM-DD)
- `--before DATA` - Sincronizza email prima di questa data (YYYY-MM-DD)
- `--label LABEL` - Sincronizza solo email con questa label Gmail
- `--limit N` - Mostra massimo N differenze (default: 20)
- `--show-duplicates` - Mostra analisi dettagliata dei duplicati usando hash del contenuto

**Cosa Succede Durante la Sincronizzazione:**
1. **Scarica & Confronta**: Scarica i metadati da entrambi gli account con progresso visivo
2. **Copia Mancanti**: Copia le email che esistono in ORIGINE ma non in DESTINAZIONE
3. **Elimina Extra**: Chiede se vuoi eliminare le email in DESTINAZIONE che non esistono in ORIGINE
4. **Rimuovi Duplicati**: Trova e rimuove automaticamente le email duplicate dalla DESTINAZIONE (mantiene la più vecchia)
5. **Riepilogo**: Mostra tempi dettagliati e risultati

---

## 🔧 Uso Avanzato

### Variabili d'Ambiente

- `GMAIL_COPY_TOOL_DEBUG=1`: Abilita il logging dettagliato per debug

### Automazione con il Flag --yes

Usa il flag `--yes` per eseguire sincronizzazioni senza alcuna interazione utente:

```bash
# Sincronizzazione completamente automatica (perfetto per task programmati)
gmail-copy-tool sync account-origine account-destinazione --yes
```

Questo:
- Auto-conferma il prompt iniziale di sincronizzazione
- Elimina automaticamente tutte le email extra senza chiedere
- Rimuove automaticamente i duplicati
- Esegue dall'inizio alla fine con zero input utente

Perfetto per task programmati o elaborazione batch!

### Gestione Duplicati

Lo strumento rileva e rimuove automaticamente i duplicati durante la sincronizzazione:
- **Rilevamento**: Usa l'impronta digitale (subject + from + date + allegati) per trovare email identiche
- **Rimozione**: Mantiene la copia più vecchia, elimina il resto
- **Solo Destinazione**: Rimuove i duplicati solo dall'account DESTINAZIONE, ORIGINE non viene mai modificato
- **Automatico**: Nessuna configurazione necessaria, avviene durante ogni sincronizzazione

---

## 🧪 Testing

### Test Unitari
```bash
pytest tests/test_*.py -v
```

---

## ❓ Risoluzione Problemi

### Le email non appaiono in Gmail

Le email copiate potrebbero non essere visibili immediatamente nell'interfaccia web di Gmail. Prova:
- Aggiorna la pagina (Ctrl+F5)
- Controlla nella cartella "Tutti i messaggi"
- Aspetta qualche minuto per la sincronizzazione

### Errori di autenticazione

Se ricevi errori di autenticazione:
```bash
# Riconfigura l'account
gmail-copy-tool setup
```

L'applicazione ora gestisce automaticamente i token scaduti/revocati, richiederà la ri-autenticazione quando necessario.

### Limiti API Gmail

Google limita il numero di richieste API. Se ricevi errori di rate limiting:
- L'applicazione riproverà automaticamente (fino a 5 tentativi con backoff esponenziale)
- Aspetta qualche minuto prima di riprovare

### Comando non trovato

Se vedi "comando non trovato" o "command not found":
1. Assicurati di aver attivato l'ambiente virtuale:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
2. Verifica di aver installato lo strumento: `pip install -e .`

---

## 📁 File di Configurazione

I file vengono salvati in `~/.gmail-copy-tool/`:
- `config.json` - Configurazione degli account
- `token_*.json` - Token di autenticazione OAuth

---

## 💡 Aiuto

Per aiuto su qualsiasi comando:
```bash
gmail-copy-tool COMANDO --help
```

Per esempio:
```bash
gmail-copy-tool sync --help
gmail-copy-tool setup --help
```
