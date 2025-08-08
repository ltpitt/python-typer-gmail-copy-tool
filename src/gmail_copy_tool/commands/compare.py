import os
import logging
import base64
import email
import os
import logging
import base64
import email
import hashlib
from datetime import datetime

import typer
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()

def normalize_date(date_str):
    """Normalize date string to YYYY/MM/DD for Gmail search queries."""
    if not date_str:
        return None
    date_str = date_str.strip()
    fmts = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y/%m/%d")
        except ValueError:
            continue
    try:
        import email.utils
        parsed_tuple = email.utils.parsedate_tz(date_str)
        if parsed_tuple:
            dt = datetime.utcfromtimestamp(email.utils.mktime_tz(parsed_tuple))
            return dt.strftime("%Y/%m/%d")
    except Exception:
        pass
    raise ValueError(f"Invalid date format: {date_str}")

def compute_canonical_hash_from_gmailclient(client, msg_id):
    try:
        msg = client.service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
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
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to get canonical hash for {msg_id}: {e}")
        return None, None

def build_canonical_hash_to_id(client, ids):
    mapping = {}
    for msg_id in ids:
        h, _ = compute_canonical_hash_from_gmailclient(client, msg_id)
        if h:
            mapping[h] = msg_id
    return mapping

def get_all_message_ids(client, label=None, after=None, before=None):
    service = client.service
    user_id = "me"
    message_ids = []
    page_token = None
    query = ""
    if after:
        after_norm = normalize_date(after)
        query += f" after:{after_norm}"
    if before:
        before_norm = normalize_date(before)
        query += f" before:{before_norm}"
    if label:
        label_ids = [label]
    else:
        label_ids = None
    logger = logging.getLogger(__name__)
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

@app.command()
def compare(
    source: str = typer.Option(..., help="Source Gmail account email address"),
    target: str = typer.Option(..., help="Target Gmail account email address"),
    credentials_source: str = typer.Option("credentials_source.json", help="Path to source account credentials file (default: credentials_source.json)"),
    credentials_target: str = typer.Option("credentials_target.json", help="Path to target account credentials file (default: credentials_target.json)"),
    token_source: str = typer.Option(None, help="Path to OAuth token file for source account (optional)"),
    token_target: str = typer.Option(None, help="Path to OAuth token file for target account (optional)"),
    label: str = typer.Option(None, help="Compare only emails with this Gmail label"),
    after: str = typer.Option(None, help="Compare emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Compare emails before this date (YYYY-MM-DD)")
):
    """Compare source and target accounts. Verifies all emails are copied (hash-based)."""
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    logger = logging.getLogger(__name__)
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")
        logger.debug(f"Source: {source}, Target: {target}")
        logger.debug(f"Credentials source: {credentials_source}, Credentials target: {credentials_target}")
    if not debug_mode:
        logging.getLogger("gmail_copy_tool.core.gmail_client").setLevel(logging.WARNING)
    source_client = GmailClient(source, credentials_path=credentials_source, token_path=token_source)
    target_client = GmailClient(target, credentials_path=credentials_target, token_path=token_target)
    if debug_mode:
        logger.debug("Fetching all message IDs for source...")
    source_ids_list = get_all_message_ids(source_client, label=label, after=after, before=before)
    if debug_mode:
        logger.debug(f"Source IDs: {source_ids_list}")
        logger.debug("Fetching all message IDs for target...")
    target_ids_list = get_all_message_ids(target_client, label=label, after=after, before=before)
    if debug_mode:
        logger.debug(f"Target IDs: {target_ids_list}")
        logger.debug("Building canonical hash-to-id map for source...")
    source_hash_to_id = build_canonical_hash_to_id(source_client, source_ids_list)
    if debug_mode:
        logger.debug(f"Source canonical hash-to-id: {source_hash_to_id}")
        logger.debug("Building canonical hash-to-id map for target...")
    target_hash_to_id = build_canonical_hash_to_id(target_client, target_ids_list)
    if debug_mode:
        logger.debug(f"Target canonical hash-to-id: {target_hash_to_id}")
    source_hashes = set(source_hash_to_id.keys())
    target_hashes = set(target_hash_to_id.keys())
    missing_in_target = source_hashes - target_hashes
    extra_in_target = target_hashes - source_hashes
    if debug_mode:
        logger.debug(f"Source canonical hashes: {source_hashes}")
        logger.debug(f"Target canonical hashes: {target_hashes}")
        logger.debug(f"Missing in target: {missing_in_target}")
        logger.debug(f"Extra in target: {extra_in_target}")
    console = Console(force_terminal=True)
    summary_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=True)
    summary_table.add_column("Metric", style="bold", justify="right")
    summary_table.add_column("Value", style="bold green", justify="left")
    summary_table.add_row("Total in source", str(len(source_hashes)))
    summary_table.add_row("Total in target", str(len(target_hashes)))
    summary_table.add_row("Missing in target", str(len(missing_in_target)))
    summary_table.add_row("Extra in target", str(len(extra_in_target)))
    console.print(Panel(summary_table, title="📊 Comparison Summary", border_style="cyan", padding=(1,2)))
    if missing_in_target:
        if debug_mode:
            logger.debug("Building missing in target table...")
        table = Table(show_header=True, header_style="bold red", show_lines=True, box=SIMPLE)
        table.add_column("Hash", style="dim")
        table.add_column("Subject")
        for h in list(missing_in_target)[:10]:
            msg_id = source_hash_to_id[h]
            _, parsed = compute_canonical_hash_from_gmailclient(source_client, msg_id)
            subject = parsed.get("Subject", "") if parsed else ""
            table.add_row(h, subject)
        console.print(Panel(table, title="Missing in Target (sample)", border_style="red", padding=(1,2)))
    if extra_in_target:
        if debug_mode:
            logger.debug("Building extra in target table...")
        table = Table(show_header=True, header_style="bold yellow", show_lines=True, box=SIMPLE)
        table.add_column("Hash", style="dim")
        table.add_column("Subject")
        for h in list(extra_in_target)[:10]:
            msg_id = target_hash_to_id[h]
            _, parsed = compute_canonical_hash_from_gmailclient(target_client, msg_id)
            subject = parsed.get("Subject", "") if parsed else ""
            table.add_row(h, subject)
        console.print(Panel(table, title="Extra in Target (sample)", border_style="yellow", padding=(1,2)))