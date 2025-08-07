import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import email.mime.text
import logging
from unittest.mock import MagicMock, Mock, patch
import pytest
from typer.testing import CliRunner
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from gmail_copy_tool.main import app
import base64
import email
import hashlib
import os
import time
import uuid
import datetime
from gmail_copy_tool.utils.gmail_api_helpers import send_with_backoff
import gmail_copy_tool.core.gmail_client as gmail_client_mod


logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Load sensitive test config from tests/test_config.json (excluded by .gitignore)
import json
import os
config_path = os.path.join(os.path.dirname(__file__), "test_config.json")
with open(config_path) as f:
    _test_config = json.load(f)

SOURCE = _test_config["SOURCE"]
TARGET = _test_config["TARGET"]
CRED_SOURCE = _test_config["CRED_SOURCE"]
CRED_TARGET = _test_config["CRED_TARGET"]
TOKEN_SOURCE = _test_config["TOKEN_SOURCE"]
TOKEN_TARGET = _test_config["TOKEN_TARGET"]


def create_test_email(service, subject, body, to_addr, from_addr, label_ids=None, date=None):
    message = email.mime.text.MIMEText(body)
    message['to'] = to_addr
    message['from'] = from_addr
    message['subject'] = subject
    if date:
        message['Date'] = date
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_func = lambda: service.users().messages().send(userId='me', body={'raw': raw}).execute()
    msg = send_with_backoff(send_func)
    if label_ids and msg:
        service.users().messages().modify(userId='me', id=msg['id'], body={'addLabelIds': label_ids}).execute()
    return msg


def compute_canonical_hash_from_gmail(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
    raw = msg.get("raw")
    if not raw:
        return None, None
    raw_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
    parsed = email.message_from_bytes(raw_bytes)
    headers = []
    for k, v in sorted(parsed.items()):
        headers.append(f"{k.lower().strip()}: {v.strip()}")
    body_parts = []
    if parsed.is_multipart():
        for part in parsed.walk():
            if part.is_multipart():
                continue
            payload = part.get_payload(decode=True) or b""
            ctype = part.get_content_type()
            fname = part.get_filename() or ""
            body_parts.append(f"{ctype}|{fname}|{hashlib.sha256(payload).hexdigest()}")
    else:
        payload = parsed.get_payload(decode=True) or b""
        ctype = parsed.get_content_type()
        body_parts.append(f"{ctype}|{hashlib.sha256(payload).hexdigest()}")
    canonical = "\n".join(headers + body_parts)
    hash_val = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return hash_val, parsed


def ensure_token(token_file, credentials_file, scope):
    if not os.path.exists(token_file):
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, ["https://mail.google.com/"])
        creds = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(creds.to_json())


def wipe_mailbox(token_file):
    creds = Credentials.from_authorized_user_file(token_file)
    service = build('gmail', 'v1', credentials=creds)
    user_id = 'me'
    message_ids = []
    page_token = None
    while True:
        results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=True).execute()
        messages = results.get('messages', [])
        message_ids.extend(msg['id'] for msg in messages)
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    for msg_id in message_ids:
        try:
            service.users().messages().delete(userId=user_id, id=msg_id).execute()
        except Exception:
            pass


def create_test_email_with_message_id(service, subject, body, to_addr, from_addr, message_id):
    message = email.mime.text.MIMEText(body)
    message['to'] = to_addr
    message['from'] = from_addr
    message['subject'] = subject
    message['Message-ID'] = message_id
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_func = lambda: service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return send_with_backoff(send_func)


def get_message_ids(service, label_ids=None, after=None):
    user_id = 'me'
    ids = set()
    page_token = None
    while True:
        results = service.users().messages().list(userId=user_id, pageToken=page_token, labelIds=label_ids, includeSpamTrash=True).execute()
        messages = results.get('messages', [])
        for msg in messages:
            msg_id = msg['id']
            msg_meta = service.users().messages().get(userId=user_id, id=msg_id, format='metadata').execute()
            msg_date = None
            msgid = None
            for h in msg_meta.get('payload', {}).get('headers', []):
                if h.get('name', '').lower() == 'message-id':
                    msgid = h.get('value')
                if h.get('name', '').lower() == 'date':
                    msg_date = h.get('value')
            if after and msg_date:
                try:
                    msg_dt = datetime.datetime.strptime(msg_date, '%a, %d %b %Y %H:%M:%S %z')
                    after_dt = datetime.datetime.strptime(after, '%a, %d %b %Y %H:%M:%S +0000').replace(tzinfo=msg_dt.tzinfo)
                    if msg_dt > after_dt and msgid:
                        ids.add(msgid)
                except Exception:
                    pass
            elif msgid:
                ids.add(msgid)
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return ids


def find_message_by_msgid(service, msgid):
    """
    Find a message by its Message-ID in the Gmail account.
    """
    user_id = 'me'
    page_token = None
    while True:
        results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=True).execute()
        messages = results.get('messages', [])
        for msg in messages:
            msg_meta = service.users().messages().get(userId=user_id, id=msg['id'], format='metadata').execute()
            for h in msg_meta.get('payload', {}).get('headers', []):
                if h.get('name', '').lower() == 'message-id' and h.get('value') == msgid:
                    return msg['id']
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return None


def get_message_count(service):
    """
    Get the total number of messages in the Gmail account.
    """
    user_id = 'me'
    results = service.users().messages().list(userId=user_id, includeSpamTrash=True).execute()
    return len(results.get('messages', []))


def fetch_all_message_ids(service, user_id='me', label_ids=None):
    ids = []
    page_token = None
    while True:
        results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=True, labelIds=label_ids).execute()
        messages = results.get('messages', [])
        ids.extend(msg['id'] for msg in messages)
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return ids


def delete_all_emails(service):
    """Helper function to delete all emails in a Gmail account."""
    user_id = 'me'
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        message_ids = fetch_all_message_ids(service, user_id)
        if not message_ids:
            break

        for msg_id in message_ids:
            try:
                service.users().messages().delete(userId=user_id, id=msg_id).execute()
            except Exception:
                pass
        # Wait for Gmail to process deletions
        time.sleep(5)

    # Explicitly empty Trash and Spam folders
    for label in ['TRASH', 'SPAM']:
        ids = fetch_all_message_ids(service, user_id, label_ids=[label])
        for msg_id in ids:
            try:
                service.users().messages().delete(userId=user_id, id=msg_id).execute()
            except Exception:
                pass

    # Final check to ensure mailbox is empty
    remaining = fetch_all_message_ids(service, user_id)
    if remaining:
        raise Exception(f"Failed to delete all emails. Remaining messages: {len(remaining)}")


@pytest.fixture(scope="function")
def setup_mailboxes():
    ensure_token(TOKEN_SOURCE, CRED_SOURCE, "mail.google.com")
    ensure_token(TOKEN_TARGET, CRED_TARGET, "mail.google.com")
    wipe_mailbox(TOKEN_SOURCE)
    wipe_mailbox(TOKEN_TARGET)
    yield
    wipe_mailbox(TOKEN_SOURCE)
    wipe_mailbox(TOKEN_TARGET)


def test_copy_preserves_custom_labels(setup_mailboxes):
    """
    Test that custom labels on source emails are preserved in the target after migration.
    """
    # Create a custom label in source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    label_name = f"TestLabel-{uuid.uuid4()}"
    label_obj = service_source.users().labels().create(userId='me', body={"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}).execute()
    custom_label_id = label_obj['id']
    # Create a test email with the custom label
    test_email = create_test_email(service_source, "Label Preservation", "Body", SOURCE, SOURCE, label_ids=[custom_label_id])
    time.sleep(1)
    # Patch GmailClient to always use mail.google.com
    original_init = gmail_client_mod.GmailClient.__init__
    def patched_init(self, account, credentials_path="credentials.json", token_path=None, scope=None):
        return original_init(self, account, credentials_path, token_path, scope="mail.google.com")
    gmail_client_mod.GmailClient.__init__ = patched_init
    # Run copy
    runner = CliRunner()
    args = [
        "copy",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--token-source", TOKEN_SOURCE,
        "--token-target", TOKEN_TARGET,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    # In target, find the migrated message by Message-ID and check for a label with the same name
    creds_target = Credentials.from_authorized_user_file(TOKEN_TARGET)
    service_target = build('gmail', 'v1', credentials=creds_target)
    # Get Message-ID of the test email
    msg_meta = service_source.users().messages().get(userId='me', id=test_email['id'], format='metadata').execute()
    msgid = None
    for h in msg_meta.get('payload', {}).get('headers', []):
        if h.get('name', '').lower() == 'message-id':
            msgid = h.get('value')
            break
    assert msgid, "Test email Message-ID not found"
    # Find the migrated message in target
    migrated_msg_id = find_message_by_msgid(service_target, msgid)
    assert migrated_msg_id, "Migrated message not found in target"
    # Get labels in target
    target_labels = service_target.users().labels().list(userId='me').execute().get('labels', [])
    target_label_names = {l['name'] for l in target_labels}
    assert label_name in target_label_names, f"Label '{label_name}' not found in target account labels: {target_label_names}"
    # Check that the migrated message has the label
    migrated_msg = service_target.users().messages().get(userId='me', id=migrated_msg_id, format='metadata').execute()
    migrated_label_ids = set(migrated_msg.get('labelIds', []))
    # Find the label id in target by name
    target_label_id = next((l['id'] for l in target_labels if l['name'] == label_name), None)
    assert target_label_id and target_label_id in migrated_label_ids, f"Migrated message does not have label '{label_name}' in target"


def test_delete_command(setup_mailboxes):
    """
    Test the delete functionality by creating emails, deleting them using the helper function, and verifying the mailbox is empty.
    """
    # Create test emails in source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    test_emails = [
        {"subject": "DeleteTest 1", "body": "Body 1"},
        {"subject": "DeleteTest 2", "body": "Body 2"},
    ]
    for email_data in test_emails:
        create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE)
        time.sleep(1)

    # Use the helper function to delete all emails
    delete_all_emails(service_source)

    # Wait for Gmail to process deletions
    time.sleep(15)

    # Verify mailbox is empty
    count = get_message_count(service_source)
    assert count == 0, f"Mailbox not empty after delete operation, found {count} messages"


def test_copy_and_compare_real_accounts(setup_mailboxes):
    """
    Test copying and comparing all emails between real accounts.
    """
    # Create a known set of test emails
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    test_emails = [
        {"subject": "Test 1", "body": "Body 1"},
        {"subject": "Test 2", "body": "Body 2"},
        {"subject": "Test 3", "body": "Body 3"},
    ]
    for email_data in test_emails:
        create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE)
        time.sleep(1)
    # Patch GmailClient in this test to always use read-write scope for both source and target
    original_init = gmail_client_mod.GmailClient.__init__
    def patched_init(self, account, credentials_path="credentials.json", token_path=None, scope=None):
        return original_init(self, account, credentials_path, token_path, scope="mail.google.com")
    gmail_client_mod.GmailClient.__init__ = patched_init
    # Run the copy command with real credentials
    runner = CliRunner()
    args = [
        "copy",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--token-source", TOKEN_SOURCE,
        "--token-target", TOKEN_TARGET,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Copy operation completed." in result.output
    # Run the compare command with real credentials
    args = [
        "compare",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--token-source", TOKEN_SOURCE,
        "--token-target", TOKEN_TARGET,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Comparison Summary" in result.output

    # --- MIME-based verification ---
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    creds_target = Credentials.from_authorized_user_file(TOKEN_TARGET)
    service_target = build('gmail', 'v1', credentials=creds_target)

    def get_all_gmail_ids(service):
        ids = []
        page_token = None
        while True:
            results = service.users().messages().list(userId='me', pageToken=page_token, includeSpamTrash=True).execute()
            messages = results.get('messages', [])
            ids.extend(msg['id'] for msg in messages)
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return ids

    source_ids = get_all_gmail_ids(service_source)
    target_ids = get_all_gmail_ids(service_target)


def test_copy_and_compare_date_filter(setup_mailboxes):
    """
    Test copying and comparing only emails after a certain date.
    """
    # Initialize service_source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)

    # Date filter: only emails after this date should be copied
    after_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime('%a, %d %b %Y %H:%M:%S +0000')
    test_emails = [
        {"subject": "Old Email", "body": "Old", "date": (datetime.datetime.utcnow() - datetime.timedelta(days=2)).strftime('%a, %d %b %Y %H:%M:%S +0000')},
        {"subject": "New Email", "body": "New", "date": (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime('%a, %d %b %Y %H:%M:%S +0000')},
    ]
    for email_data in test_emails:
        create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE, date=email_data["date"])
        time.sleep(1)

    # Patch GmailClient to always use mail.google.com
    import gmail_copy_tool.core.gmail_client as gmail_client_mod
    original_init = gmail_client_mod.GmailClient.__init__
    def patched_init(self, account, credentials_path="credentials.json", token_path=None, scope=None):
        return original_init(self, account, credentials_path, token_path, scope="mail.google.com")
    gmail_client_mod.GmailClient.__init__ = patched_init

    # Run copy with --after <after_date>
    runner = CliRunner()
    args = [
        "copy",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--token-source", TOKEN_SOURCE,
        "--token-target", TOKEN_TARGET,
        "--after", after_date,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output

    # Run compare with --after <after_date>
    args = [
        "compare",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--token-source", TOKEN_SOURCE,
        "--token-target", TOKEN_TARGET,
        "--after", after_date,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output

    # Compare Message-IDs for emails after the date
    source_msgids = get_message_ids(service_source, after=after_date)
    creds_target = Credentials.from_authorized_user_file(TOKEN_TARGET)
    service_target = build('gmail', 'v1', credentials=creds_target)
    target_msgids = get_message_ids(service_target, after=after_date)
    missing_msgids = sorted(list(source_msgids - target_msgids))

    assert not missing_msgids, f"Date filter: {len(missing_msgids)} messages missing in target! Message-IDs: {missing_msgids}"


def test_copy_with_invalid_credentials():
    """
    Test error handling when invalid credentials are provided.
    """
    from typer.testing import CliRunner
    runner = CliRunner()
    from gmail_copy_tool.main import app
    args = [
        "copy",
        "--source", "invalid@example.com",
        "--target", "invalid2@example.com",
        "--credentials-source", "nonexistent.json",
        "--credentials-target", "nonexistent2.json",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert "credentials" in result.output.lower() or "error" in result.output.lower()

def test_delete_duplicates_content_based(setup_mailboxes):
    """
    Test the delete-duplicates CLI command by creating emails with identical content but different Message-IDs,
    and verifying only unique emails remain based on content.
    """
    # Create duplicate test emails in source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    test_emails = [
        {"subject": "DuplicateTest 1", "body": "Body 1"},
        {"subject": "DuplicateTest 1", "body": "Body 1"},
        {"subject": "DuplicateTest 2", "body": "Body 2"},
        {"subject": "DuplicateTest 2", "body": "Body 2"},
    ]
    for email_data in test_emails:
        create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE)
        time.sleep(1)

    # Log the created emails
    unique_emails = get_message_ids(service_source)
    print(f"[DEBUG] Created emails (Message-IDs): {unique_emails}")

    # Run delete-duplicates CLI command
    runner = CliRunner()
    args = [
        "delete-duplicates",
        "--account", SOURCE,
        "--credentials", CRED_SOURCE,
        "--token", TOKEN_SOURCE,
    ]
    result = runner.invoke(app, args)
    print(f"[DEBUG] CLI command output: {result.output}")
    assert result.exit_code == 0, result.output

    # Fetch Gmail internal email IDs instead of Message-ID values
    unique_emails = [msg['id'] for msg in service_source.users().messages().list(userId='me', includeSpamTrash=True).execute().get('messages', [])]
    print(f"[DEBUG] Remaining emails after deduplication (Gmail IDs): {unique_emails}")

    # Debugging: Fetch email content to verify deduplication logic
    for email_id in unique_emails:
        email_meta = service_source.users().messages().get(userId='me', id=email_id, format='full').execute()
        headers = email_meta.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), None)
        body = email_meta.get('snippet', '')
        print(f"[DEBUG] Email ID: {email_id}, Subject: {subject}, Body Snippet: {body}")

    # Verify only unique emails remain
    assert len(unique_emails) == 2, f"Expected 2 unique emails, found {len(unique_emails)}"


def test_analyze_command(setup_mailboxes):
    """
    Test the analyze CLI command by creating emails and verifying the count.
    """
    # Create test emails in source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    test_emails = [
        {"subject": "AnalyzeTest 1", "body": "Body 1"},
        {"subject": "AnalyzeTest 2", "body": "Body 2"},
        {"subject": "AnalyzeTest 3", "body": "Body 3"},
    ]
    for email_data in test_emails:
        create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE)
        time.sleep(1)

    # Run analyze CLI command
    runner = CliRunner()
    args = [
        "analyze",
        "--account", SOURCE,
        "--credentials", CRED_SOURCE,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Total emails: 3" in result.output, f"Unexpected output: {result.output}"


def test_resume_copy_command(tmp_path, setup_mailboxes):
    """
    Test that the copy command resumes from a checkpoint and does not re-copy already migrated emails.
    """
    import shutil
    from gmail_copy_tool.utils.checkpoint import Checkpoint

    # Create test emails in source
    creds_source = Credentials.from_authorized_user_file(TOKEN_SOURCE)
    service_source = build('gmail', 'v1', credentials=creds_source)
    test_emails = [
        {"subject": "ResumeTest 1", "body": "Body 1"},
        {"subject": "ResumeTest 2", "body": "Body 2"},
        {"subject": "ResumeTest 3", "body": "Body 3"},
    ]
    msgids = []
    msgid_to_gmailid = {}
    for email_data in test_emails:
        msg = create_test_email(service_source, email_data["subject"], email_data["body"], SOURCE, SOURCE)
        time.sleep(1)
        # Get Message-ID
        msg_meta = service_source.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
        for h in msg_meta.get('payload', {}).get('headers', []):
            if h.get('name', '').lower() == 'message-id':
                msgids.append(h.get('value'))
                msgid_to_gmailid[h.get('value')] = msg['id']
                break


    # Simulate interruption: actually copy the first email to the target, then mark as copied in the checkpoint
    checkpoint_path = tmp_path / "resume_checkpoint.json"
    # Copy the correct first email (matching msgids[0]) manually to the target
    creds_target = Credentials.from_authorized_user_file(TOKEN_TARGET)
    service_target = build('gmail', 'v1', credentials=creds_target)
    first_gmail_id = msgid_to_gmailid[msgids[0]]
    first_msg = service_source.users().messages().get(userId='me', id=first_gmail_id, format='raw').execute()
    raw = first_msg['raw']
    service_target.users().messages().insert(userId='me', body={'raw': raw}).execute()
    # Now mark as copied in checkpoint
    cp = Checkpoint(str(checkpoint_path))
    cp.mark_copied(msgids[0])

    # Patch GmailClient to always use mail.google.com
    import gmail_copy_tool.core.gmail_client as gmail_client_mod
    original_init = gmail_client_mod.GmailClient.__init__
    def patched_init(self, account, credentials_path="credentials.json", token_path=None, scope=None, checkpoint_path_override=None):
        return original_init(self, account, credentials_path, token_path, scope="mail.google.com")
    gmail_client_mod.GmailClient.__init__ = patched_init

    # Run copy with checkpoint
    runner = CliRunner()
    args = [
        "copy",
        "--source", SOURCE,
        "--target", TARGET,
        "--credentials-source", CRED_SOURCE,
        "--credentials-target", CRED_TARGET,
        "--checkpoint", str(checkpoint_path),
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output

    # In target, check that all emails are present
    creds_target = Credentials.from_authorized_user_file(TOKEN_TARGET)
    service_target = build('gmail', 'v1', credentials=creds_target)
    target_msgids = get_message_ids(service_target)
    for msgid in msgids:
        assert msgid in target_msgids, f"Message-ID {msgid} missing in target after resume copy"

