# python-typer-gmail-copy-tool

A CLI tool built with [Typer](https://typer.tiangolo.com/) that allows you to analyze, copy, compare, and clean emails between Gmail accounts. Designed for reliability, resumability, and data integrity.

---

## 📌 Features

- Analyze total email count in a Gmail account
- Copy all emails (including attachments and metadata) from one Gmail account to another
- Resume interrupted copy operations automatically
- Compare source and target accounts to verify copy success
- Delete emails from source that already exist in target
- Modular CLI interface with clear commands

---

## 🚀 Installation

```bash
pip install typer google-api-python-client oauth2client

1. Enable the Gmail API in your Google Cloud Console.
2. Create OAuth 2.0 credentials.
3. Download `credentials.json` and place it in your working directory.

### How to obtain `credentials.json` for Gmail API access

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services > Library** and enable the **Gmail API**.
4. Go to **APIs & Services > Credentials**.
5. Click **Create Credentials** > **OAuth client ID**.
   - If prompted, configure the OAuth consent screen first.
   - Choose **Desktop app** as the application type.
   - Name it (e.g., "gmail-copy-tool").
6. Click **Create**. Download the `credentials.json` file.
7. Place `credentials.json` in your project’s working directory (where you run the CLI).

This file allows your app to request user authorization for Gmail access.

---

## 🛠️ Configuration

The tool uses OAuth 2.0 for Gmail access. On first run, it will prompt for authorization and store tokens locally.

- `credentials.json`: OAuth client credentials
- `token_source.json`: Token for source account
- `token_target.json`: Token for target account
- `.gmail-copy-checkpoint.json`: Stores last copied message ID for resume functionality

---

## 📚 Usage

Run any command with `--help` to see options:
```bash
gmail-copy-tool --help
```

---

## 🧪 CLI Commands

### `analyze`

```bash
gmail-copy-tool analyze --account source@gmail.com
```

Counts total number of emails in the specified Gmail account.

---

### `copy`

```bash
gmail-copy-tool copy --source source@gmail.com --target target@gmail.com
```

Copies all emails from the source account to the target account.

- Includes attachments, labels, and metadata
- Automatically resumes if interrupted
- Skips already-copied messages using message ID tracking

---

### `compare`

```bash
gmail-copy-tool compare --source source@gmail.com --target target@gmail.com
```

Compares source and target accounts to verify that all emails have been copied.

- Uses Gmail message IDs for comparison
- Reports missing or mismatched messages

---

### `delete-duplicates`

```bash
gmail-copy-tool delete-duplicates --source source@gmail.com --target target@gmail.com
```

Deletes emails from the source account that already exist in the target account.

- Safe operation: only deletes exact matches
- Useful for cleanup after migration

---

## 🧠 Behavioral Details

- **Resume Mechanism**: Stores last copied message ID in `.gmail-copy-checkpoint.json`. On restart, resumes from that point.
- **Comparison Logic**: Uses Gmail message IDs to detect duplicates and verify integrity.
- **Data Copied**:
  - Email body
  - Attachments
  - Labels
  - Thread metadata
- **Excluded Data**:
  - Spam folder
  - Trash folder
  - Drafts

---

## 🧪 Development Notes

- Built with [Typer](https://typer.tiangolo.com/) for intuitive CLI design
- Uses `google-api-python-client` for Gmail access
- Modular structure for easy extension

---

## 🧩 Future Enhancements

- Add filters (by label, date, sender)
- Support dry-run mode
- Add concurrency for large inboxes
- Export logs and reports

---

## 🧑‍💻 Contributing

Pull requests welcome. Please ensure code is typed and tested.

---

## 📄 License

MIT License
