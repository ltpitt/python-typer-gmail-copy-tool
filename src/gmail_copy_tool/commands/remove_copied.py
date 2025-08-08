
import typer
import logging
import sys
import base64
import email
import hashlib
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def compute_canonical_hash_from_gmailclient(client, msg_id):
    try:
        msg = client.service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
        raw = msg.get("raw")
        if not raw:
            return None
        raw_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
        parsed = email.message_from_bytes(raw_bytes)
        # Only include key headers for canonicalization
        key_headers = ["from", "to", "subject", "date", "message-id"]
        headers = []
        for k, v in sorted(parsed.items()):
            k_lower = k.lower().strip()
            if k_lower in key_headers:
                headers.append(f"{k_lower}: {v.strip()}")
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
        return hash_val
    except Exception as e:
        logger.error(f"Failed to get canonical hash for {msg_id}: {e}")
        return None

def get_all_message_ids(client):
    service = client.service
    user_id = "me"
    message_ids = []
    page_token = None
    while True:
        try:
            results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=False).execute()
            messages = results.get("messages", [])
            message_ids.extend(msg["id"] for msg in messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    return message_ids

@app.command()
def remove_copied(
    source: str = typer.Option(..., help="Source Gmail account (emails will be removed from here)"),
    target: str = typer.Option(..., help="Target Gmail account (emails present here will be removed from source)"),
    credentials_source: str = typer.Option(..., help="Path to OAuth client credentials JSON file for source account"),
    credentials_target: str = typer.Option(..., help="Path to OAuth client credentials JSON file for target account"),
    token_source: str = typer.Option(None, help="Path to OAuth token file for source account (optional)"),
    token_target: str = typer.Option(None, help="Path to OAuth token file for target account (optional)")
):
    """Remove from the source account all emails that are present in the target account (based on canonical hash comparison)."""
    logger.info(f"Connecting to source ({source}) and target ({target}) accounts...")
    source_client = GmailClient(source, credentials_source, token_source)
    target_client = GmailClient(target, credentials_target, token_target)
    logger.info("Fetching all message IDs from source account...")
    source_ids = get_all_message_ids(source_client)
    logger.info(f"Source account has {len(source_ids)} messages.")
    logger.info("Fetching all message IDs from target account...")
    target_ids = get_all_message_ids(target_client)
    logger.info(f"Target account has {len(target_ids)} messages.")
    logger.info("Building canonical hash set for target account...")
    target_hashes = set()
    for msg_id in target_ids:
        h = compute_canonical_hash_from_gmailclient(target_client, msg_id)
        if h:
            target_hashes.add(h)
    logger.info(f"Target account has {len(target_hashes)} unique canonical hashes.")
    logger.info("Checking source messages for removal...")
    removed_count = 0
    for msg_id in source_ids:
        h = compute_canonical_hash_from_gmailclient(source_client, msg_id)
        if h and h in target_hashes:
            try:
                source_client.service.users().messages().delete(userId="me", id=msg_id).execute()
                logger.info(f"Removed email from source (ID: {msg_id}) present in target.")
                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove email {msg_id}: {e}")
    logger.info(f"Finished. Removed {removed_count} emails from source account that were present in target.")
