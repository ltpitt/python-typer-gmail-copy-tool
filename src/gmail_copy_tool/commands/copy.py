import os
import logging
import re
import time
from datetime import datetime

import typer
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()
logger = logging.getLogger(__name__)

@app.command()
def copy(
    source: str = typer.Option(..., help="Source Gmail account email address"),
    target: str = typer.Option(..., help="Target Gmail account email address"),
    credentials_source: str = typer.Option("credentials_source.json", help="Path to source account credentials file (default: credentials_source.json)"),
    credentials_target: str = typer.Option("credentials_target.json", help="Path to target account credentials file (default: credentials_target.json)"),
    label: str = typer.Option(None, help="Copy only emails with this Gmail label"),
    after: str = typer.Option(None, help="Copy emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Copy emails before this date (YYYY-MM-DD)"),
    checkpoint: str = typer.Option(None, help="Path to checkpoint file for resume support (optional)")
):
    """Copy all emails from the source account to the target account."""
    # Enable debug logging if GMAIL_COPY_TOOL_DEBUG=1
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")
    typer.echo(f"Copying emails: {source} -> {target}")
    try:
        logger.debug(f"Source account: {source}, credentials file: {credentials_source}")
        typer.secho("[ACTION REQUIRED] Please enter authentication data for the SOURCE account.", fg=typer.colors.BLUE, bold=True)
        source_client = GmailClient(source, credentials_path=credentials_source, scope="readonly")
        logger.debug(f"Target account: {target}, credentials file: {credentials_target}")
        typer.secho("[ACTION REQUIRED] Please enter authentication data for the TARGET account.", fg=typer.colors.BLUE, bold=True)
        # Use highest permission for target
        target_client = GmailClient(target, credentials_path=credentials_target, scope="mail.google.com")

        # Print the account email argument and the credentials email for both source and target
        import jwt
        def get_email_from_creds(client):
            try:
                creds = getattr(client, 'creds', None)
                if creds and hasattr(creds, 'id_token') and creds.id_token:
                    payload = jwt.decode(creds.id_token, options={"verify_signature": False})
                    return payload.get("email")
                if creds and hasattr(creds, 'service_account_email'):
                    return creds.service_account_email
                if creds and hasattr(creds, 'email'):
                    return creds.email
            except Exception as e:
                logger.debug(f"Could not extract email from credentials: {e}")
            return None
        source_email = get_email_from_creds(source_client)
        target_email = get_email_from_creds(target_client)
        logger.debug(f"Source account argument: {source}")
        logger.debug(f"Source credentials email: {source_email}")
        logger.debug(f"Target account argument: {target}")
        logger.debug(f"Target credentials email: {target_email}")


        # Fetch all message IDs from source (with optional filters)
        source_ids = _get_all_message_ids(source_client, label=label, after=after, before=before)
        typer.echo(f"Total emails to copy: {len(source_ids)}")
        logger.debug(f"Fetched {len(source_ids)} message IDs from source.")
        if debug_mode:
            logger.debug(f"Source message IDs: {source_ids}")

        # --- Checkpoint logic ---
        if checkpoint:
            from gmail_copy_tool.utils.checkpoint import Checkpoint
            cp = Checkpoint(checkpoint)
        else:
            cp = None

        # Fetch all Message-ID headers from target account for deduplication
        logger.info("Fetching Message-ID headers from target account for deduplication...")
        target_ids = _get_all_message_ids(target_client)
        target_msgids = set()
        for t_id in target_ids:
            try:
                t_meta = target_client.service.users().messages().get(userId="me", id=t_id, format="metadata").execute()
                for h in t_meta.get('payload', {}).get('headers', []):
                    if h.get('name', '').lower() == 'message-id':
                        target_msgids.add(h.get('value'))
                        break
            except Exception as e:
                logger.debug(f"Failed to fetch target message metadata for {t_id}: {e}")
        logger.info(f"Found {len(target_msgids)} Message-ID headers in target account.")

        # --- Label preservation logic ---
        # Fetch all labels from source and target
        source_labels = source_client.service.users().labels().list(userId="me").execute().get('labels', [])
        target_labels = target_client.service.users().labels().list(userId="me").execute().get('labels', [])
        source_label_id_to_name = {l['id']: l['name'] for l in source_labels}
        target_label_name_to_id = {l['name']: l['id'] for l in target_labels}

        # For custom labels, create in target if missing, and build mapping
        label_map = {}  # source_label_id -> target_label_id
        for src_label in source_labels:
            name = src_label['name']
            if name in target_label_name_to_id:
                label_map[src_label['id']] = target_label_name_to_id[name]
            else:
                # Only create user labels (not system labels)
                if src_label['type'] == 'user':
                    body = {
                        "name": name,
                        "labelListVisibility": src_label.get("labelListVisibility", "labelShow"),
                        "messageListVisibility": src_label.get("messageListVisibility", "show")
                    }
                    try:
                        created = target_client.service.users().labels().create(userId="me", body=body).execute()
                        label_map[src_label['id']] = created['id']
                        target_label_name_to_id[name] = created['id']
                    except Exception as e:
                        logger.warning(f"Could not create label '{name}' in target: {e}")
                else:
                    # System label, just map if present
                    if name in target_label_name_to_id:
                        label_map[src_label['id']] = target_label_name_to_id[name]

        # Progress bar for copy operation
        copied_count = 0
        with Progress(
            TextColumn("[bold blue]Copying emails..."),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("copy", total=len(source_ids))
            for idx, msg_id in enumerate(source_ids, 1):
                try:
                    logger.debug(f"Copying message {idx}/{len(source_ids)}: {msg_id}")
                    # Fetch source message metadata to get subject, Message-ID, and labels
                    src_meta = source_client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
                    src_subject = None
                    src_msgid = None
                    src_label_ids = set(src_meta.get('labelIds', []))
                    for h in src_meta.get('payload', {}).get('headers', []):
                        if h.get('name', '').lower() == 'subject':
                            src_subject = h.get('value')
                        if h.get('name', '').lower() == 'message-id':
                            src_msgid = h.get('value')
                    logger.debug(f"Source message {msg_id} subject: {src_subject}")
                    logger.debug(f"Source message {msg_id} Message-ID: {src_msgid}")
                    logger.debug(f"Source message {msg_id} labelIds: {src_label_ids}")
                    logger.info(f"Source message {msg_id}: subject={src_subject}, Message-ID={src_msgid}, labelIds={src_label_ids}")

                    # Resume/skip logic: skip if already copied in checkpoint
                    if cp and src_msgid and cp.is_copied(src_msgid):
                        logger.info(f"Skipping message {msg_id} (Message-ID: {src_msgid}) - already marked as copied in checkpoint.")
                        progress.update(task, advance=1)
                        continue

                    # Deduplication check
                    if src_msgid and src_msgid in target_msgids:
                        logger.info(f"Skipping message {msg_id} (Message-ID: {src_msgid}) - already exists in target.")
                        if cp and src_msgid:
                            cp.mark_copied(src_msgid)
                        progress.update(task, advance=1)
                        continue

                    # Fetch raw message for copying
                    message = source_client.service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
                    src_raw_b64 = message.get('raw', '')
                    logger.debug(f"Source message {msg_id} raw (base64, first 200 chars): {src_raw_b64[:200]}...")
                    try:
                        import base64
                        src_raw_bytes = base64.urlsafe_b64decode(src_raw_b64.encode('utf-8'))
                        logger.debug(f"Source message {msg_id} raw (decoded, first 500 chars): {src_raw_bytes[:500]!r}...")
                    except Exception as e:
                        logger.warning(f"Could not decode source raw for {msg_id}: {e}")

                    response = target_client.service.users().messages().insert(userId="me", body={"raw": src_raw_b64}).execute()
                    logger.debug(f"Insert response for {msg_id}: {response}")
                    copied_count += 1

                    # Mark as copied in checkpoint after successful copy
                    if cp and src_msgid:
                        cp.mark_copied(src_msgid)

                    # Fetch and log the raw MIME of the inserted message in the target
                    tgt_msg_id = response.get('id')
                    if tgt_msg_id:
                        try:
                            tgt_raw_msg = target_client.service.users().messages().get(userId="me", id=tgt_msg_id, format="raw").execute()
                            tgt_raw_b64 = tgt_raw_msg.get('raw', '')
                            logger.debug(f"Target message {tgt_msg_id} raw (base64, first 200 chars): {tgt_raw_b64[:200]}...")
                            try:
                                tgt_raw_bytes = base64.urlsafe_b64decode(tgt_raw_b64.encode('utf-8'))
                                logger.debug(f"Target message {tgt_msg_id} raw (decoded, first 500 chars): {tgt_raw_bytes[:500]!r}...")
                            except Exception as e:
                                logger.warning(f"Could not decode target raw for {tgt_msg_id}: {e}")
                        except Exception as e:
                            logger.warning(f"Could not fetch target raw for {tgt_msg_id}: {e}")

                    # Assign labels in target
                    tgt_msg_id = response.get('id')

                    if tgt_msg_id and src_label_ids:
                        # Map source label IDs to target label IDs
                        # Only assign user labels and assignable system labels
                        ASSIGNABLE_SYSTEM_LABELS = {
                            'INBOX', 'UNREAD', 'STARRED', 'IMPORTANT', 'TRASH', 'SPAM', 'CATEGORY_PERSONAL',
                            'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'
                        }
                        NON_ASSIGNABLE_SYSTEM_LABELS = {'SENT', 'DRAFT', 'OUTBOX', 'CHAT'}
                        mapped_label_ids = []
                        for lid in src_label_ids:
                            label_name = source_label_id_to_name.get(lid)
                            logger.info(f"Checking label: lid={lid}, name={label_name}, in NON_ASSIGNABLE_SYSTEM_LABELS={label_name in NON_ASSIGNABLE_SYSTEM_LABELS}, in label_map={lid in label_map}")
                            if label_name in NON_ASSIGNABLE_SYSTEM_LABELS:
                                logger.info(f"Skipping non-assignable system label: {label_name}")
                                continue  # skip non-assignable system labels
                            if lid in label_map:
                                # Only assign if user label, or assignable system label
                                src_label = next((l for l in source_labels if l['id'] == lid), None)
                                logger.info(f"src_label: {src_label}")
                                if src_label:
                                    logger.info(f"src_label type: {src_label['type']}, name: {label_name}")
                                    if src_label['type'] == 'user' or (src_label['type'] == 'system' and label_name in ASSIGNABLE_SYSTEM_LABELS):
                                        mapped_label_ids.append(label_map[lid])
                        logger.info(f"For message {msg_id}, mapped_label_ids to assign: {mapped_label_ids}")
                        logger.info(f"label_map: {label_map}")
                        if mapped_label_ids:
                            try:
                                resp = target_client.service.users().messages().modify(userId="me", id=tgt_msg_id, body={"addLabelIds": mapped_label_ids}).execute()
                                logger.info(f"Label assignment response for {tgt_msg_id}: {resp}")
                                logger.debug(f"Assigned labels {mapped_label_ids} to message {tgt_msg_id} in target.")
                                # --- Retry loop to ensure label is present (Gmail eventual consistency) ---
                                max_retries = 10
                                for attempt in range(max_retries):
                                    tgt_msg = target_client.service.users().messages().get(userId="me", id=tgt_msg_id, format="metadata").execute()
                                    tgt_label_ids = set(tgt_msg.get('labelIds', []))
                                    logger.info(f"Attempt {attempt+1}: tgt_label_ids for {tgt_msg_id}: {tgt_label_ids}")
                                    if all(lid in tgt_label_ids for lid in mapped_label_ids):
                                        logger.info(f"All mapped_label_ids present on target message {tgt_msg_id}")
                                        break
                                    time.sleep(2)
                                else:
                                    logger.warning(f"Labels {mapped_label_ids} not confirmed on message {tgt_msg_id} after retries.")
                            except Exception as e:
                                logger.warning(f"Could not assign labels to message {tgt_msg_id} in target: {e}")

                    # Fetch target message metadata to get subject (after insert)
                    tgt_subject = None
                    if tgt_msg_id:
                        try:
                            tgt_meta = target_client.service.users().messages().get(userId="me", id=tgt_msg_id, format="metadata").execute()
                            for h in tgt_meta.get('payload', {}).get('headers', []):
                                if h.get('name', '').lower() == 'subject':
                                    tgt_subject = h.get('value')
                                    break
                            logger.debug(f"Target message {tgt_msg_id} subject: {tgt_subject}")
                        except Exception as e:
                            logger.debug(f"Could not fetch target subject for {tgt_msg_id}: {e}")
                    if debug_mode:
                        logger.debug(f"Target message inserted: {response.get('id')}, threadId: {response.get('threadId')}, labelIds: {response.get('labelIds')}")
                except Exception as e:
                    logger.error(f"Failed to copy message {msg_id}: {e}")
                progress.update(task, advance=1)
            # Ensure progress bar reaches 100%
            progress.update(task, completed=len(source_ids))
        # Print summary in a visually separated row, outside the progress context
        print()  # Add a blank line for separation
        typer.secho("─" * 60, fg=typer.colors.BLUE)
        typer.secho(f"Copy operation completed. Total copied: {copied_count}", fg=typer.colors.GREEN, bold=True)
        typer.secho("─" * 60, fg=typer.colors.BLUE)
        logger.debug(f"Copy operation completed. Total copied: {copied_count}")
    except FileNotFoundError as e:
        missing_file = None
        if 'credentials_source' in str(e) or credentials_source in str(e):
            missing_file = credentials_source
        elif 'credentials_target' in str(e) or credentials_target in str(e):
            missing_file = credentials_target
        if missing_file:
            typer.secho(f"ERROR: Credentials file not found: {missing_file}\nPlease provide a valid credentials file.", fg=typer.colors.RED, bold=True)
        else:
            typer.secho("ERROR: Credentials file not found (source or target). Please check your credential file paths.", fg=typer.colors.RED, bold=True)
        import sys; sys.stdout.flush(); sys.stderr.flush()
    except ValueError as e:
        # Let Typer handle ValueError for test mocks
        raise
    except typer.Exit as e:
        logger.error(f"Copy command exited with code: {e.exit_code}")
        raise
    except Exception as e:
        logger.exception(f"Error during copy: {e}")
        typer.secho(f"ERROR: {str(e)} (credentials issue or other error)", fg=typer.colors.RED, bold=True)
        import sys; sys.stdout.flush(); sys.stderr.flush()


def _get_all_message_ids(client, label=None, after=None, before=None):
    """Fetch all message IDs from a GmailClient with optional filters."""
    service = client.service
    user_id = "me"
    message_ids = []
    page_token = None
    query = ""
    def normalize_date(date_str):
        # Accept YYYY-MM-DD or YYYY/MM/DD, output YYYY/MM/DD
        if not date_str:
            return None
        if re.match(r"^\d{4}/\d{2}/\d{2}$", date_str):
            return date_str
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str.replace("-", "/")
        # Try to parse RFC 2822 and convert to YYYY/MM/DD
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.strftime("%Y/%m/%d")
        except Exception:
            pass
        return date_str

    if after:
        after_norm = normalize_date(after)
        logger.debug(f"Formatted 'after' date for query: {after_norm}")
        query += f" after:{after_norm}"
    if before:
        before_norm = normalize_date(before)
        query += f" before:{before_norm}"
    if label:
        label_ids = [label]
    else:
        label_ids = None
    while True:
        try:
            results = service.users().messages().list(
                userId=user_id,
                pageToken=page_token,
                includeSpamTrash=False,
                q=query if query else None,
                labelIds=label_ids
            ).execute()
            messages = results.get("messages", [])
            message_ids.extend(msg["id"] for msg in messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    return message_ids
