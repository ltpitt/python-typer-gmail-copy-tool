import typer
import logging
import sys
from gmail_copy_tool.core.gmail_client import GmailClient
from gmail_copy_tool.utils.canonicalization import compute_canonical_hash

app = typer.Typer()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

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
    """Delete from source all emails present in target (by Message-ID)."""
    logger.info(f"Connecting to source ({source}) and target ({target}) accounts...")
    source_client = GmailClient(source, credentials_source, token_source)
    target_client = GmailClient(target, credentials_target, token_target)
    logger.info("Fetching all message IDs from source account...")
    source_ids = get_all_message_ids(source_client)
    logger.info(f"Source account has {len(source_ids)} messages.")
    logger.info("Fetching all message IDs from target account...")
    target_ids = get_all_message_ids(target_client)
    logger.info(f"Target account has {len(target_ids)} messages.")
    logger.info("Building Message-ID set for target account...")
    target_msgids = set()
    for msg_id in target_ids:
        try:
            t_meta = target_client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
            for h in t_meta.get('payload', {}).get('headers', []):
                if h.get('name', '').lower() == 'message-id':
                    target_msgids.add(h.get('value'))
                    break
        except Exception as e:
            logger.error(f"Failed to fetch Message-ID for target email {msg_id}: {e}")

    logger.info(f"Target account has {len(target_msgids)} unique Message-IDs.")
    logger.info("Checking source messages for removal...")
    removed_count = 0
    for msg_id in source_ids:
        try:
            s_meta = source_client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
            s_msgid = None
            for h in s_meta.get('payload', {}).get('headers', []):
                if h.get('name', '').lower() == 'message-id':
                    s_msgid = h.get('value')
                    break
            if s_msgid and s_msgid in target_msgids:
                source_client.service.users().messages().delete(userId="me", id=msg_id).execute()
                logger.info(f"Removed email from source (ID: {msg_id}) present in target.")
                removed_count += 1
        except Exception as e:
            logger.error(f"Failed to remove email {msg_id}: {e}")

    logger.info(f"Finished. Removed {removed_count} emails from source account that were present in target.")
