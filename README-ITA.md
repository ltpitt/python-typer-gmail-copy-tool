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

## Comandi

### Elenca Account Configurati

```bash
gmail-copy-tool list
```

Mostra tutti gli account che hai configurato.

### Sincronizza Email

```bash
gmail-copy-tool sync ACCOUNT_ORIGINE ACCOUNT_DESTINAZIONE
```

Sincronizza le email dall'account di origine all'account di destinazione. Il comando:
- Confronta i due account usando un'impronta digitale del contenuto (subject + from + date + attachments)
- Copia le email mancanti nella destinazione
- Chiede se vuoi eliminare le email extra dalla destinazione

**Esempi:**
```bash
# Sincronizza tutti
gmail-copy-tool sync vecchio nuovo

# Sincronizza solo email del 2024
gmail-copy-tool sync vecchio nuovo --year 2024

# Sincronizza email in un intervallo di date
gmail-copy-tool sync vecchio nuovo --after 2024-01-01 --before 2024-06-30

# Sincronizza email con una label specifica
gmail-copy-tool sync vecchio nuovo --label "Importante"
```

**Opzioni:**
- `--year ANNO` - Sincronizza solo email di un anno specifico
- `--after DATA` - Sincronizza email dopo questa data (YYYY-MM-DD)
- `--before DATA` - Sincronizza email prima di questa data (YYYY-MM-DD)
- `--label LABEL` - Sincronizza solo email con questa label Gmail
- `--limit N` - Mostra massimo N differenze (default: 20)

## Esempi d'Uso

### Scenario 1: Migrazione Completa

```bash
# Configura gli account
gmail-copy-tool setup

# Sincronizza tutto da "vecchio" a "nuovo"
gmail-copy-tool sync vecchio nuovo

# Il comando ti chiederà interattivamente:
# - Se copiare le email mancanti nella destinazione
# - Se eliminare le email extra dalla destinazione
```

### Scenario 2: Sincronizzazione Anno Specifico

```bash
# Sincronizza solo le email del 2024
gmail-copy-tool sync vecchio nuovo --year 2024
```

### Scenario 3: Verifica Differenze

```bash
# Mostra solo le prime 10 differenze senza modificare nulla
gmail-copy-tool sync vecchio nuovo --limit 10
# (Non specificare --sync per modalità solo-lettura)
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

L'applicazione ora gestisce automaticamente i token scaduti/revocati, richiederà la ri-autenticazione quando necessario.

### Limiti API Gmail

Google limita il numero di richieste API. Se ricevi errori di rate limiting:
- L'applicazione riproverà automaticamente
- Aspetta qualche minuto prima di riprovare

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
