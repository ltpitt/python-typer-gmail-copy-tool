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

### For Normal Users

To install the tool as a normal user, run:

```bash
pip install .
```

This will install the tool and its dependencies in your environment.

### For Developers

To install the tool in editable mode for development, run:

```bash
pip install -e .
```

This will allow you to make changes to the source code and immediately test them without reinstalling the package.

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
gmail-copy-tool analyze --account source@gmail.com --token-file token_source.json
```

Counts total number of emails in the specified Gmail account. Uses explicit token file for safety.

---

### `copy`

```bash
gmail-copy-tool copy --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Copies all emails from the source account to the target account.

- Includes attachments, labels, and metadata
- Automatically resumes if interrupted
- Skips already-copied messages using message ID tracking
- Uses explicit token files for safety and repeatability

---

### `compare`

```bash
gmail-copy-tool compare --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Compares source and target accounts to verify that all emails have been copied.

- Uses canonical hashes for robust comparison (ignores Gmail-injected headers)
- Reports missing or mismatched messages

---

### `remove-copied`

```bash
gmail-copy-tool remove-copied --source source@gmail.com --target target@gmail.com --source-token token_source.json --target-token token_target.json
```

Removes from the source account all emails that are present in the target account (based on canonical hash comparison).

- Safe operation: only deletes emails confirmed present in the target
- Only emails that were actually copied are deleted; extra emails remain
- Useful for cleanup after migration to avoid duplicates in the source

---

## 🧾 Example Test Config & Testing

An example config file (`tests/test_config_example.json`) is provided to help users run integration tests and automate CLI commands.

**Fields:**
- `source_account`: Gmail address to copy from
- `target_account`: Gmail address to copy to
- `source_token`: OAuth token file for source
- `target_token`: OAuth token file for target
- `source_credentials`: Credentials file for source
- `target_credentials`: Credentials file for target
- `label`: (optional) Gmail label to filter
- `after`: (optional) Only emails after this date (YYYY-MM-DD)
- `before`: (optional) Only emails before this date (YYYY-MM-DD)

**Usage:**
- Edit the fields to match your Gmail accounts and token/credential files.
- After editing, rename the file to `tests/test_config.json` to run integration tests. The test runner will only use `test_config.json`.

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

Integration tests in `tests/test_integration.py` robustly verify all major CLI commands:

- **Setup:** Both source and target mailboxes are wiped and populated with known emails before each test.
- **Assertions:** All data integrity checks use canonical hashes, ignoring Gmail-injected headers for reliability.
- **Coverage:**
  - `copy`: Asserts all emails are copied, with hashes matching between source and target.
  - `compare`: Asserts source and target hashes match after migration.
  - `remove-copied`: Asserts only emails that were copied are deleted from source, extra emails remain.
  - `delete-duplicates`: Asserts only true duplicates are deleted, using hash-based matching.

---

## 🧠 Behavioral Details

- **Resume Mechanism**: Stores last copied message ID in `.gmail-copy-checkpoint.json`. On restart, resumes from that point.
- **Comparison Logic**: Uses canonical hashes (ignoring Gmail-injected headers) for robust integrity verification and deduplication.
- **Data Copied:**
  - Email body
  - Attachments
  - Labels
  - Thread metadata
- **Excluded Data:**
  - Spam folder
  - Trash folder
  - Drafts

---

## ⚙️ Environment Variables

- `GMAIL_COPY_TOOL_DEBUG=1`: Enables debug logging for troubleshooting and development. Shows detailed progress and internal state.

---

## 🛠️ Troubleshooting

- If you see authentication prompts, ensure your token files are present and valid.
- For IndentationError or import errors, check for duplicate/conflicting code blocks and clean up your source files.
- For noisy logs, set `GMAIL_COPY_TOOL_DEBUG=0` (default) for production use.

---

## ⚠️ Gmail API Limitations & Reliability Notes

This tool is designed to work reliably with the Gmail API, but several limitations and quirks must be considered:

- **Message Comparison:** Gmail can inject headers, modify MIME structure, or change message IDs during migration. Direct comparison by ID or raw content is unreliable. This tool uses canonical hashing (ignoring injected headers and non-essential fields) to robustly verify message integrity across accounts.
- **API Consistency:** Gmail API operations (copy, delete, label) may not be immediately reflected. Integration tests use explicit waits (sleep) after such operations to ensure changes are visible before verification. This is essential for reliable automated testing and migration.
- **Rate Limits & Quotas:** Gmail API enforces strict rate limits. The tool implements exponential backoff and retries for sending and modifying messages. If you hit rate limits, the tool will wait and retry automatically, but large migrations may require patience.
- **Partial Failures:** Gmail API may occasionally fail or return transient errors. All operations are designed to be resumable and idempotent. If interrupted, you can safely rerun commands; only missing or unprocessed messages will be handled.
- **Labeling & Metadata:** Gmail may delay the application of labels or metadata changes. Tests and migration logic include explicit waits and repeated checks to confirm changes.
- **Token & Permission Issues:** If tokens expire or permissions change, re-authentication is required. The tool will prompt for re-authorization as needed.

**Best Practices:**
- Always use explicit token/config files for safety and repeatability.
- Expect delays and be patient with large inboxes or bulk operations.
- Use canonical hash-based comparison for true data integrity.
- Review logs for warnings/errors and retry if needed.

---

## 🧪 Development Notes

- Built with [Typer](https://typer.tiangolo.com/) for intuitive CLI design
- Uses `google-api-python-client` for Gmail access
- Modular structure for easy extension
- Professional logging: only warnings/errors shown to users, debug/info in debug mode
- All CLI commands accept explicit token file options for safety and repeatability
- All integration tests assert true data integrity using canonical hashes

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
