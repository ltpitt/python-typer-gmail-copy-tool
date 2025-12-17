import time
import logging
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

def send_with_backoff(send_func, max_retries=5, initial_delay=2, *args, **kwargs):
    """Send Gmail API request with exponential backoff."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempting to send email (attempt {attempt+1})")
            result = send_func(*args, **kwargs)
            time.sleep(1)  # Be gentle: add a small delay between sends
            return result
        except Exception as e:
            # Check for rate limit error
            if hasattr(e, 'resp') and hasattr(e.resp, 'status') and e.resp.status == 429:
                retry_after = None
                if hasattr(e.resp, 'get'):
                    retry_after = e.resp.get('Retry-After')
                # Extract Google error message if available
                google_error_msg = str(e)
                retry_after_utc = None
                if hasattr(e, 'content'):
                    try:
                        import json
                        content = e.content.decode() if isinstance(e.content, bytes) else e.content
                        data = json.loads(content)
                        google_error_msg = data.get('error', {}).get('message', str(e))
                    except Exception:
                        pass
                print(f"Google API error message: {google_error_msg}", flush=True)
                logger.info(f"Google API error message: {google_error_msg}")
                # Try to parse retry timestamp from Google error message
                import re
                match = re.search(r'Retry after ([0-9T:\.\-Z]+)', google_error_msg)
                if match:
                    retry_after_utc = match.group(1)
                wait_seconds = None
                now = time.time()
                SAFETY_MARGIN = 5  # seconds
                if retry_after:
                    wait_seconds = int(retry_after) + SAFETY_MARGIN
                elif retry_after_utc:
                    from datetime import datetime, timezone
                    try:
                        retry_time = datetime.strptime(retry_after_utc, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                    except ValueError:
                        retry_time = datetime.strptime(retry_after_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    now_dt = datetime.now(timezone.utc)
                    wait_seconds = max(1, int((retry_time - now_dt).total_seconds()) + SAFETY_MARGIN)
                else:
                    wait_seconds = delay
                next_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now + wait_seconds))
                msg = f"Rate limit hit when sending email. "
                if retry_after:
                    msg += f"Google suggests retry at {retry_after_utc} UTC. "
                else:
                    msg += "No Retry-After header or retry time present from Google. "
                    logger.info("No Retry-After header or retry time present from Google. Using exponential backoff.")
                    print("No Retry-After header or retry time present from Google. Using exponential backoff.", flush=True)
                msg += f"Retrying after {wait_seconds} seconds (at {next_time})."
                logger.warning(msg)
                print(msg, flush=True)  # Always print to stdout for pytest visibility
                time.sleep(wait_seconds)
                delay = min(delay * 2, 60)  # Exponential backoff, max 60s
            else:
                logger.error(f"Failed to send email: {e}")
                print(f"Failed to send email: {e}", flush=True)
                break
    else:
        logger.error(f"Giving up on sending email after {max_retries} attempts.")
        print(f"Giving up on sending email after {max_retries} attempts.", flush=True)
        return None

def ensure_token(token_path, credentials_path, scope):
    """
    Ensure a valid token exists at the specified path. If not, create one using the credentials file.

    Args:
        token_path (str): Path to the token file.
        credentials_path (str): Path to the credentials file.
        scope (str): The scope for the Gmail API.

    Returns:
        None
    """
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, [scope])
            if creds and creds.valid:
                return
        except Exception:
            pass

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, [scope])
    creds = flow.run_local_server(port=0)
    with open(token_path, 'w') as token_file:
        token_file.write(creds.to_json())
