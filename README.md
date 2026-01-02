# Gmail Copy Tool

A simple, powerful CLI tool for managing Gmail accounts: copy emails, verify transfers, and clean up duplicates.

---

## ✨ Quick Start (Step-by-Step for Beginners)

### 1. Download and Open the Project

1. Download or clone this project to your computer
2. Open a terminal/command prompt
3. Navigate to the project folder:
   ```bash
   cd path\to\python-typer-gmail-copy-tool
   ```

### 2. Create and Activate Virtual Environment

**On Windows:**
```bash
# Create virtual environment (only needed once)
python -m venv .venv

# Activate it (do this every time you open a new terminal)
.venv\Scripts\activate
```

**On Mac/Linux:**
```bash
# Create virtual environment (only needed once)
python3 -m venv .venv

# Activate it (do this every time you open a new terminal)
source .venv/bin/activate
```

You'll know it's activated when you see `(.venv)` at the start of your terminal line.

### 3. Install the Tool

```bash
pip install -e .
```

This installs the `gmail-copy-tool` command.

### 4. Setup Your Accounts

Run the interactive setup wizard to configure your Gmail accounts:

```bash
gmail-copy-tool setup
```

The wizard will:
- Guide you through creating OAuth credentials in Google Cloud Console
- Help you authenticate with your Gmail accounts
- Save your accounts with easy-to-remember nicknames (e.g., "old-account", "new-account")

### 5. Start Using It!

```bash
# Sync all emails from one account to another (interactive)
gmail-copy-tool sync old-account new-account

# Sync only emails from 2024
gmail-copy-tool sync old-account new-account --year 2024

# Fully automated sync (no questions asked)
gmail-copy-tool sync old-account new-account --yes

# See your configured accounts
gmail-copy-tool list
```

**Remember:** Always activate the virtual environment first! If you see "command not found", run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux).

---
Beginner Friendly**: Clear step-by-step instructions, no complex commands
- **Simple Setup**: Interactive wizard guides you through OAuth setup
- **Easy Commands**: Use account nicknames instead of email addresses and file paths
- **Auto Token Refresh**: Automatically handles expired/revoked tokens
- **Interactive Sync**: Compare, copy missing emails, and clean up extras in one command
- **Automatic Duplicate Removal**: Finds and removes duplicate emails from target account
- **Non-Interactive Mode**: Use `--yes` flag for fully automated sync
- **Visual Progress Bars**: Beautiful real-time progress indicators
- **Year Shortcuts**: Quickly filter by year with `--year 2024`
- **Content-Based Comparison**: Uses fingerprint (subject+from+date+attachments) to detect differences
- **Batch Processing**: Handles thousands of emails efficiently with smart rate limiting
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
Shows you total vs unique email counts (detects duplicates)
- Copies missing emails to TARGET
- Interactively asks if you want to delete extra emails from TARGET (or auto-deletes with `--yes`)
- **Automatically removes duplicate emails from TARGET** (keeps oldest copy)
- Shows beautiful real-time progress bars for all operations
- Displays detailed performance timing summary
```bash
gmail-copy-tool sync SOURCE TARGET [OPTIONS]
```

Synchronize emails from SOURCE to TARGET account. The command:
- Compares both accounts using content-based fingerprint (Message-ID + subject + from + attachments)
- Shows you total vs unique email counts (detects duplicates)
- Copies missing emails to TARGET
- Interactively asks if you want to delete extra emails from TARGET (or auto-deletes with `--yes`)
- **Automatically removes duplicate emails from TARGET** (keeps oldest copy)
- Shows beautiful real-time progress bars for all operations
- Displays detailed performance timing summary

**📋 Complete Command (Copy-Paste Ready):**

**Windows (PowerShell):**
```powershell
.venv\Scripts\activate; $env:GMAIL_COPY_TOOL_DEBUG="1"; gmail-copy-tool sync SOURCE TARGET --yes
```

**Mac/Linux:**
```bash
source .venv/bin/activate && GMAIL_COPY_TOOL_DEBUG=1 gmail-copy-tool sync SOURCE TARGET --yes
```

Replace `SOURCE` and `TARGET` with your account nicknames (e.g., `old-account` and `new-account`).

This command:
- ✅ Automatically activates the virtual environment
- ✅ Enables debug mode for detailed logs
- ✅ Runs fully automated sync (no questions asked)

Examples:
```bash
# Sync all emails
gmail-copy-tool sync old-account new-account

# Sync only 2024 emails
gmail-copy-tool sync old-account new-account --year 2024

# Fully automated sync (no prompts, auto-confirm all)
gmail-copy-tool sync old-account new-account --yes
```

**Options:**
- `--yes` / `-y` - Auto-confirm all prompts (non-interactive mode for automation)
- `--year YEAR` - Sync only emails from a specific year
- `--after DATE` - Sync emails after this date (YYYY-MM-DD)
- `--before DATE` - Sync emails before this date (YYYY-MM-DD)  
- `--label LABEL` - Sync only emails with this Gmail label
- `--limit N` - Show maximum N differences (default: 20)
- `--show-duplicates` - Show detailed duplicate analysis using content hash

**What Happens During Sync:**
1. **Fetch & Compare**: Downloads metadata from both accounts with visual progress
2. **Copy Missing**: Copies emails that exist in SOURCE bu

### Automation with --yes Flag

Use the `--yes` flag to run syncs without any user interaction:

```bash
# Fully automated sync (perfect for scheduled tasks)
gmail-copy-tool sync source-account target-account --yes
```

This will:
- Auto-confirm the initial sync prompt
- Automatically delete all extra emails without asking
- Automatically remove duplicates
- Run from start to finish with zero user input

Perfect for scheduled tasks or batch processing!

### Handling Duplicates

The tool automatically detects and removes duplicates during sync:
- **Detection**: Uses fingerprint (subject + from + date + attachments) to find identical emails
- **Removal**: Keeps the oldest copy, deletes the rest
- **Target Only**: Only removes duplicates from TARGET account, SOURCE is never modified
- **Automatic**: No configuration needed, happens during every synct not in TARGET
3. **Delete Extras**: Asks if you want to delete emails in TARGET that don't exist in SOURCE
4. **Remove Duplicates**: Automatically finds and removes duplicate emails from TARGET (keeps oldest)
5. **Summary**: Shows detailed timing and results
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
