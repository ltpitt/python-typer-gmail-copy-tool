import time
import logging

logger = logging.getLogger(__name__)

def send_with_backoff(send_func, max_retries=5, initial_delay=2, *args, **kwargs):
    """
    Call a Gmail API send function with exponential backoff and Retry-After support.
    send_func: function to call (e.g., service.users().messages().send(...).execute)
    *args, **kwargs: arguments to pass to send_func
    """
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
                    now_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
                    wait_seconds = max(1, int((retry_time - now_dt).total_seconds()) + SAFETY_MARGIN)
                else:
                    wait_seconds = delay
                next_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now + wait_seconds))
                msg = f"Rate limit hit when sending email. "
                if retry_after:
                    google_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now + int(retry_after)))
                    msg += (f"Google suggests retry after {retry_after} seconds (at {google_time}). ")
                elif retry_after_utc:
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
