# Gmail Copy Tool

A simple, powerful CLI tool for managing Gmail accounts: copy emails, verify transfers, and clean up duplicates.

---

## ✨ Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Setup Your Accounts

Run the interactive setup wizard to configure your Gmail accounts:

```bash
gmail-copy-tool setup
```

The wizard will:
- Guide you through creating OAuth credentials in Google Cloud Console
- Help you authenticate with your Gmail accounts
- Save your accounts with easy-to-remember nicknames (e.g., "old-account", "new-account")

### 3. Start Using It!

```bash
# Sync all emails from one account to another (interactive)
gmail-copy-tool sync old-account new-account

# Sync only emails from 2024
gmail-copy-tool sync old-account new-account --year 2024

# See your configured accounts
gmail-copy-tool list
```

That's it! No more long command lines with credential paths.

---

## 📌 Features

- **Simple Setup**: Interactive wizard guides you through OAuth setup
- **Easy Commands**: Use account nicknames instead of email addresses and file paths
- **Auto Token Refresh**: Automatically handles expired/revoked tokens
- **Interactive Sync**: Compare, copy missing emails, and clean up extras in one command
- **Year Shortcuts**: Quickly filter by year with `--year 2024`
- **Content-Based Comparison**: Uses fingerprint (subject+from+date+attachments) to detect differences

---

## 🔐 Getting OAuth Credentials

Before you can use this tool, you need to create OAuth credentials in Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API**:
   - Navigate to **APIs & Services > Library**
   - Search for "Gmail API" and click **Enable**
4. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Configure the consent screen if prompted
   - Choose **Desktop app** as the application type
   - Download the credentials JSON file
5. When running `gmail-copy-tool setup`, provide the path to this credentials file

The setup wizard will guide you through the rest!

---

## 📚 Commands

### Setup Wizard
```bash
gmail-copy-tool setup
```
Interactive wizard to add Gmail accounts. You'll need:
- OAuth credentials JSON file (see above)
- Access to the Gmail account to authorize

### List Accounts
```bash
gmail-copy-tool list
```
Show all configured accounts with their nicknames and email addresses.

### Sync Emails
```bash
gmail-copy-tool sync SOURCE TARGET [OPTIONS]
```

Synchronize emails from SOURCE to TARGET account. The command:
- Compares both accounts using content-based fingerprint (subject + from + date + attachments)
- Copies missing emails to TARGET
- Interactively asks if you want to delete extra emails from TARGET

Examples:
```bash
# Sync all emails
gmail-copy-tool sync old-account new-account

# Sync only 2024 emails
gmail-copy-tool sync old-account new-account --year 2024

# Sync emails from a specific date range
gmail-copy-tool sync old-account new-account --after 2024-01-01 --before 2024-06-30

# Sync emails with a specific label
gmail-copy-tool sync old-account new-account --label "Important"

# Show first 10 differences only (no changes made)
gmail-copy-tool sync old-account new-account --limit 10
```

**Options:**
- `--year YEAR` - Sync only emails from a specific year
- `--after DATE` - Sync emails after this date (YYYY-MM-DD)
- `--before DATE` - Sync emails before this date (YYYY-MM-DD)  
- `--label LABEL` - Sync only emails with this Gmail label
- `--limit N` - Show maximum N differences (default: 20)
- `--show-duplicates` - Show detailed duplicate analysis using content hash

---

## 🔧 Advanced Usage

### Environment Variables

- `GMAIL_COPY_TOOL_DEBUG=1`: Enable detailed debug logging

---

## 🧪 Testing

### Unit Tests
```bash
pytest tests/test_*.py -v
```

### Integration Tests
1. Create `tests/test_config.json`:
```json
{
  "source_account": "source@gmail.com",
  "target_account": "target@gmail.com",
  "source_token": "token_source.json",
  "target_token": "token_target.json",
  "source_credentials": "credentials_source.json",
  "target_credentials": "credentials_target.json"
}
```

2. Run integration tests:
```bash
pytest tests/test_integration.py -v
```

Integration tests verify:
- Email copying with all metadata and attachments
- Resume functionality after interruption
- Canonical hash-based comparison
- Duplicate detection and removal
- Label preservation

---

## ⚙️ How It Works

### Content-Based Fingerprinting
The tool compares emails using a fingerprint composed of:
- **Subject** - Email subject line
- **From** - Sender address  
- **Date** - Timestamp (first 20 chars to handle timezone variations)
- **Attachments** - Filename and size for each attachment

This approach:
- Is more reliable than Message-ID (which can change across accounts)
- Detects true duplicates even if Message-IDs differ
- Handles Gmail's internal modifications gracefully

### Auto Token Refresh
The tool automatically handles expired or revoked OAuth tokens:
- Detects `invalid_grant` errors
- Deletes the expired token file
- Re-initiates OAuth flow for fresh credentials
- No manual intervention needed

### Data Integrity
The tool copies:
- ✅ Email body (HTML and plain text)
- ✅ All attachments
- ✅ Labels
- ✅ Thread metadata
- ❌ Spam/Trash (excluded)
- ❌ Drafts (excluded)

---

## 🐛 Troubleshooting

**"No accounts configured"**
- Run `gmail-copy-tool setup` to add accounts

**"Account not found"**
- Check `gmail-copy-tool list` to see configured accounts
- Account nicknames are case-sensitive

**Authentication prompts**
- The tool automatically handles expired/revoked tokens
- You'll be prompted to re-authenticate when needed
- Check file permissions on `~/.gmail-copy-tool/` if issues persist

**Rate limit errors**
- The tool automatically retries with exponential backoff
- For large migrations, be patient - Gmail API has strict quotas

**Emails not appearing in Gmail**
- Refresh the page (Ctrl+F5)
- Check "All Mail" folder
- Wait a few minutes for synchronization

---

## 📄 License

MIT License
