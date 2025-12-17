# Gmail Copy Tool

Strumento da riga di comando per copiare email tra account Gmail.

## Installazione

```bash
pip install -e .
```

## Configurazione Iniziale

### 1. Ottieni le Credenziali OAuth

1. Vai alla [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto o selezionane uno esistente
3. Abilita l'API Gmail (APIs & Services → Enable APIs and Services → Gmail API)
4. Crea credenziali OAuth 2.0 (APIs & Services → Credentials → Create Credentials → OAuth client ID)
5. Scarica il file JSON delle credenziali

### 2. Configura gli Account

Usa il wizard interattivo per configurare i tuoi account:

```bash
gmail-copy-tool setup
```

Il wizard ti guiderà attraverso:
- Inserimento del nome account (un nickname a tua scelta)
- Selezione del file delle credenziali OAuth
- Autenticazione con Google

I token di autenticazione vengono salvati automaticamente in `~/.gmail-copy-tool/`.

## Comandi Principali

### Elenca Account Configurati

```bash
gmail-copy-tool list
```

Mostra tutti gli account che hai configurato.

### Copia Email

```bash
gmail-copy-tool copy ACCOUNT_ORIGINE ACCOUNT_DESTINAZIONE
```

Copia tutte le email dall'account di origine all'account di destinazione.

**Esempio:**
```bash
gmail-copy-tool copy lavoro personale
```

**Opzioni:**
- `--checkpoint FILE` - Salva progressi in un file checkpoint
- `--resume FILE` - Riprende da un checkpoint precedente
- `--batch-size N` - Numero di email da processare per batch (default: 100)

### Confronta Account

```bash
gmail-copy-tool compare ACCOUNT1 ACCOUNT2
```

Confronta due account per vedere quali email sono presenti in uno ma non nell'altro.

### Analizza Account

```bash
gmail-copy-tool analyze ACCOUNT
```

Mostra statistiche sull'account (numero email, label, dimensioni).

### Rimuovi Email Copiate

```bash
gmail-copy-tool remove-copied ACCOUNT_ORIGINE ACCOUNT_DESTINAZIONE
```

Rimuove dall'origine le email già copiate nella destinazione.

### Rimuovi Duplicati

```bash
gmail-copy-tool delete-duplicates ACCOUNT
```

Trova e rimuove email duplicate nello stesso account.

## Esempi d'Uso

### Scenario 1: Copia Completa

```bash
# Configura account
gmail-copy-tool setup

# Copia tutto da "vecchio" a "nuovo" con checkpoint
gmail-copy-tool copy vecchio nuovo --checkpoint backup.json

# Verifica cosa è stato copiato
gmail-copy-tool compare vecchio nuovo
```

### Scenario 2: Ripristino da Interruzione

```bash
# Riprendi copia interrotta
gmail-copy-tool copy vecchio nuovo --resume backup.json
```

### Scenario 3: Pulizia Dopo Copia

```bash
# Copia email
gmail-copy-tool copy vecchio nuovo

# Rimuovi dall'account vecchio le email copiate
gmail-copy-tool remove-copied vecchio nuovo
```

## Risoluzione Problemi

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

### Limiti API Gmail

Google limita il numero di richieste API. Se ricevi errori di rate limiting:
- L'applicazione riproverà automaticamente
- Usa `--batch-size` più piccolo per rallentare le richieste
- Usa i checkpoint per riprendere in caso di interruzione

## File di Configurazione

I file vengono salvati in `~/.gmail-copy-tool/`:
- `config.json` - Configurazione degli account
- `token_*.json` - Token di autenticazione OAuth

## Aiuto

Per aiuto su qualsiasi comando:
```bash
gmail-copy-tool COMANDO --help
```

Per esempio:
```bash
gmail-copy-tool copy --help
gmail-copy-tool setup --help
```
