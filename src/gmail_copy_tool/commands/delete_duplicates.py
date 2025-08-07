import time
import typer
from rich import print
from gmail_copy_tool.core.gmail_client import GmailClient
import logging
import sys

app = typer.Typer()
logger = logging.getLogger(__name__)

# Configure logging to output to console
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Output logs to console
    ]
)

@app.command()
def delete_duplicates(
    account: str = typer.Option(..., help="Email account to delete duplicate emails from"),
    credentials: str = typer.Option(..., help="Path to OAuth client credentials JSON file"),
    token: str = typer.Option(None, help="Path to OAuth token file (optional)"),
):
    """Delete duplicate emails in the specified Gmail account."""
    client = GmailClient(account, credentials, token, scope="mail.google.com")
    service = client.service
    user_id = 'me'

    def fetch_all_emails_by_content_hash():
        """
        Fetch all emails for the user and group them by a hash of their content (subject + body).
        Returns:
            dict: A dictionary where keys are content hashes and values are lists of email IDs.
        """
        import hashlib

        def compute_content_hash(subject, body):
            content = f"{subject}{body}".encode('utf-8')
            return hashlib.sha256(content).hexdigest()

        ids = {}
        page_token = None
        total_emails = 0
        logger.info("Starting to fetch emails grouped by content hash...")
        while True:
            # Removed failsafe mechanism
            try:
                logger.debug(f"Fetching emails with page_token: {page_token}")
                results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=False).execute()
                messages = results.get('messages', [])
                logger.debug(f"Fetched {len(messages)} emails in this batch")
                total_emails += len(messages)
                for msg in messages:
                    msg_meta = service.users().messages().get(userId=user_id, id=msg['id'], format='full').execute()
                    msg_id = msg['id']
                    headers = msg_meta.get('payload', {}).get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
                    body = msg_meta.get('snippet', '')
                    content_hash = compute_content_hash(subject, body)
                    ids.setdefault(content_hash, []).append(msg_id)
                    logger.debug(f"Grouped email ID {msg_id} under content hash {content_hash}")
            except Exception as e:
                logger.error(f"Error fetching messages: {e}")
                break
            page_token = results.get('nextPageToken')
            logger.debug(f"Next page_token: {page_token}")
            if not page_token:
                logger.info("No more pages to fetch.")
                break
        logger.info(f"Total emails fetched: {total_emails}")
        return ids

    try:
        logger.info("Starting duplicate deletion process...")
        duplicates = fetch_all_emails_by_content_hash()
        logger.info(f"Fetched {len(duplicates)} content hash groups")
        for content_hash, msg_ids in duplicates.items():
            logger.debug(f"Processing content hash: {content_hash}, Email IDs: {msg_ids}")
            if len(msg_ids) > 1:
                logger.info(f"Found {len(msg_ids)} duplicates for content hash {content_hash}")
                for msg_id in msg_ids[1:]:
                    max_retries = 5
                    delay = 2  # Start with 2 seconds
                    for attempt in range(max_retries):
                        try:
                            logger.debug(f"Attempting to delete email ID: {msg_id} (attempt {attempt+1})")
                            service.users().messages().delete(userId=user_id, id=msg_id).execute()
                            logger.info(f"Deleted duplicate email with ID {msg_id}")
                            time.sleep(1)  # Be gentle: add a small delay between deletions
                            break
                        except Exception as e:
                            # Check for rate limit error
                            if hasattr(e, 'resp') and hasattr(e.resp, 'status') and e.resp.status == 429:
                                retry_after = None
                                if hasattr(e.resp, 'get'):
                                    retry_after = e.resp.get('Retry-After')
                                logger.warning(f"Rate limit hit when deleting {msg_id}. Retrying after {retry_after or delay} seconds.")
                                time.sleep(int(retry_after) if retry_after else delay)
                                delay = min(delay * 2, 60)  # Exponential backoff, max 60s
                            else:
                                logger.error(f"Failed to delete duplicate email {msg_id}: {e}")
                                break
                    else:
                        logger.error(f"Giving up on deleting {msg_id} after {max_retries} attempts.")
            else:
                logger.debug(f"No duplicates for content hash {content_hash}")

        logger.info(f"Duplicate email cleanup completed for {account}.")
        logger.debug("Exiting with code 0")
        raise typer.Exit(code=0)

    except Exception as e:
        import traceback
        logger.error(f"An error occurred: {e}")
        logger.error(traceback.format_exc())
        logger.debug("Exiting with code 1")
        raise typer.Exit(code=1)

    # Ensure no exception is raised after exiting
    return
