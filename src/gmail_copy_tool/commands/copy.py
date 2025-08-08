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
    token_source: str = typer.Option(None, help="Path to OAuth token file for source account (optional)"),
    token_target: str = typer.Option(None, help="Path to OAuth token file for target account (optional)"),
    label: str = typer.Option(None, help="Copy only emails with this Gmail label"),
    after: str = typer.Option(None, help="Copy emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Copy emails before this date (YYYY-MM-DD)"),
    checkpoint: str = typer.Option(None, help="Path to checkpoint file for resume support (optional)")
):
    """Copy all emails from source to target Gmail account."""
    # Enable debug logging if GMAIL_COPY_TOOL_DEBUG=1
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")
    typer.echo(f"Copying emails: {source} -> {target}")
    try:
        typer.secho("[ACTION REQUIRED] Please enter authentication data for the SOURCE account.", fg=typer.colors.BLUE, bold=True)
        source_client = GmailClient(source, credentials_path=credentials_source, token_path=token_source, scope="readonly")
        typer.secho("[ACTION REQUIRED] Please enter authentication data for the TARGET account.", fg=typer.colors.BLUE, bold=True)
        target_client = GmailClient(target, credentials_path=credentials_target, token_path=token_target, scope="mail.google.com")

        # Fetch all message IDs from source (with optional filters)
        source_ids = _get_all_message_ids(source_client, label=label, after=after, before=before)
        typer.echo(f"Total emails to copy: {len(source_ids)}")

        # --- Checkpoint logic ---
        if checkpoint:
            from gmail_copy_tool.utils.checkpoint import Checkpoint
            cp = Checkpoint(checkpoint)
        else:
            cp = None

        # Fetch all Message-ID headers from target account for deduplication
        target_ids = _get_all_message_ids(target_client)
        target_msgids = set()
        for t_id in target_ids:
            try:
                t_meta = target_client.service.users().messages().get(userId="me", id=t_id, format="metadata").execute()
                for h in t_meta.get('payload', {}).get('headers', []):
                    if h.get('name', '').lower() == 'message-id':
                        target_msgids.add(h.get('value'))
                        break
            except Exception:
                pass

        # --- Label preservation logic ---
        source_labels = source_client.service.users().labels().list(userId="me").execute().get('labels', [])
        target_labels = target_client.service.users().labels().list(userId="me").execute().get('labels', [])
        source_label_id_to_name = {l['id']: l['name'] for l in source_labels}
        target_label_name_to_id = {l['name']: l['id'] for l in target_labels}

        label_map = {}  # source_label_id -> target_label_id
        for src_label in source_labels:
            name = src_label['name']
            if name in target_label_name_to_id:
                label_map[src_label['id']] = target_label_name_to_id[name]
            else:
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
                    except Exception:
                        pass
                else:
                    if name in target_label_name_to_id:
                        label_map[src_label['id']] = target_label_name_to_id[name]

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
                    src_meta = source_client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
                    src_subject = None
                    src_msgid = None
                    src_label_ids = set(src_meta.get('labelIds', []))
                    for h in src_meta.get('payload', {}).get('headers', []):
                        if h.get('name', '').lower() == 'subject':
                            src_subject = h.get('value')
                        if h.get('name', '').lower() == 'message-id':
                            src_msgid = h.get('value')

                    if cp and src_msgid and cp.is_copied(src_msgid):
                        progress.update(task, advance=1)
                        continue

                    if src_msgid and src_msgid in target_msgids:
                        if cp and src_msgid:
                            cp.mark_copied(src_msgid)
                        progress.update(task, advance=1)
                        continue

                    message = source_client.service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
                    src_raw_b64 = message.get('raw', '')
                    try:
                        import base64
                        src_raw_bytes = base64.urlsafe_b64decode(src_raw_b64.encode('utf-8'))
                    except Exception:
                        pass

                    response = target_client.service.users().messages().insert(userId="me", body={"raw": src_raw_b64}).execute()
                    copied_count += 1

                    if cp and src_msgid:
                        cp.mark_copied(src_msgid)

                    tgt_msg_id = response.get('id')
                    if tgt_msg_id and src_label_ids:
                        ASSIGNABLE_SYSTEM_LABELS = {
                            'INBOX', 'UNREAD', 'STARRED', 'IMPORTANT', 'TRASH', 'SPAM', 'CATEGORY_PERSONAL',
                            'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'
                        }
                        NON_ASSIGNABLE_SYSTEM_LABELS = {'SENT', 'DRAFT', 'OUTBOX', 'CHAT'}
                        mapped_label_ids = []
                        for lid in src_label_ids:
                            label_name = source_label_id_to_name.get(lid)
                            if label_name in NON_ASSIGNABLE_SYSTEM_LABELS:
                                continue  # skip non-assignable system labels
                            if lid in label_map:
                                src_label = next((l for l in source_labels if l['id'] == lid), None)
                                if src_label:
                                    if src_label['type'] == 'user' or (src_label['type'] == 'system' and label_name in ASSIGNABLE_SYSTEM_LABELS):
                                        mapped_label_ids.append(label_map[lid])
                        if mapped_label_ids:
                            try:
                                target_client.service.users().messages().modify(userId="me", id=tgt_msg_id, body={"addLabelIds": mapped_label_ids}).execute()
                                max_retries = 10
                                for attempt in range(max_retries):
                                    tgt_msg = target_client.service.users().messages().get(userId="me", id=tgt_msg_id, format="metadata").execute()
                                    tgt_label_ids = set(tgt_msg.get('labelIds', []))
                                    if all(lid in tgt_label_ids for lid in mapped_label_ids):
                                        break
                                    time.sleep(2)
                            except Exception:
                                pass

                    tgt_subject = None
                    if tgt_msg_id:
                        try:
                            tgt_meta = target_client.service.users().messages().get(userId="me", id=tgt_msg_id, format="metadata").execute()
                            for h in tgt_meta.get('payload', {}).get('headers', []):
                                if h.get('name', '').lower() == 'subject':
                                    tgt_subject = h.get('value')
                                    break
                        except Exception:
                            pass
                except Exception:
                    pass
                progress.update(task, advance=1)
            progress.update(task, completed=len(source_ids))
        print()  # Add a blank line for separation
        typer.secho("─" * 60, fg=typer.colors.BLUE)
        typer.secho(f"Copy operation completed. Total copied: {copied_count}", fg=typer.colors.GREEN, bold=True)
        typer.secho("─" * 60, fg=typer.colors.BLUE)
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
        raise
    except typer.Exit as e:
        raise
    except Exception as e:
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

# Ensure the copy function is importable from this module
__all__ = ["copy"]