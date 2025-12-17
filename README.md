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
# Copy all emails from one account to another
gmail-copy-tool copy old-account new-account

# Copy only emails from 2024
gmail-copy-tool copy old-account new-account --year 2024

# Verify the copy was successful
gmail-copy-tool compare old-account new-account

# Check how many emails are in an account
gmail-copy-tool analyze new-account

# See your configured accounts
gmail-copy-tool list
```

That's it! No more long command lines with credential paths.

---

## 📌 Features

- **Simple Setup**: Interactive wizard guides you through OAuth setup
- **Easy Commands**: Use account nicknames instead of email addresses and file paths
- **Resume Support**: Automatically resumes if interrupted
- **Data Integrity**: Verifies all emails, attachments, and metadata are copied correctly
- **Year Shortcuts**: Quickly filter by year with `--year 2024`
- **Smart Comparison**: Uses canonical hashing to detect differences

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

### Copy Emails
```bash
gmail-copy-tool copy SOURCE TARGET [OPTIONS]
```

Examples:
```bash
# Copy all emails
gmail-copy-tool copy old-account new-account

# Copy only 2024 emails
gmail-copy-tool copy old-account new-account --year 2024

# Copy emails from a specific date range
gmail-copy-tool copy old-account new-account --after 2024-01-01 --before 2024-06-30

# Copy emails with a specific label
gmail-copy-tool copy old-account new-account --label "Important"
```

### Compare Accounts
```bash
gmail-copy-tool compare SOURCE TARGET [OPTIONS]
```

Verify that all emails from SOURCE exist in TARGET.

Examples:
```bash
# Compare all emails
gmail-copy-tool compare old-account new-account

# Compare only 2024 emails
gmail-copy-tool compare old-account new-account --year 2024
```

### Analyze Account
```bash
gmail-copy-tool analyze ACCOUNT [OPTIONS]
```

Count emails in an account.

Examples:
```bash
# Total email count
gmail-copy-tool analyze my-account

# Count 2024 emails
gmail-copy-tool analyze my-account --year 2024

# Count emails with a specific label
gmail-copy-tool analyze my-account --label "Work"
```

### Remove Copied Emails
```bash
gmail-copy-tool remove-copied SOURCE TARGET
```

Delete from SOURCE all emails that exist in TARGET. Useful for cleanup after migration.

⚠️ **Warning**: This permanently deletes emails. Use `compare` first to verify!

### Delete Duplicates
```bash
gmail-copy-tool delete-duplicates ACCOUNT
```

Find and delete duplicate emails in an account based on content.

⚠️ **Warning**: This permanently deletes emails.

---

## 🔧 Advanced Usage

### For Integration Tests (Legacy Mode)

The tool still supports the old explicit credential/token syntax for testing:

```bash
gmail-copy-tool copy \
  --source source@gmail.com \
  --target target@gmail.com \
  --credentials-source credentials_source.json \
  --credentials-target credentials_target.json \
  --token-source token_source.json \
  --token-target token_target.json
```

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

### Canonical Hashing
The tool uses "canonical hashing" to compare emails across accounts. This means:
- Ignores Gmail-injected headers (like `X-Gmail-Labels`)
- Normalizes date formats
- Compares based on essential content (From, To, Subject, Body, Attachments)
- Robust against Gmail's internal modifications

### Resume Mechanism
Copy operations can be interrupted and resumed:
- Progress is saved in `.gmail-copy-checkpoint.json`
- Already-copied emails are skipped on resume
- Safe to run multiple times

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

**Authentication prompts every time**
- Make sure your token files are being saved correctly
- Check file permissions on `~/.gmail-copy-tool/`

**Rate limit errors**
- The tool automatically retries with exponential backoff
- For large migrations, be patient - Gmail API has strict quotas

---

## 📄 License

MIT License
