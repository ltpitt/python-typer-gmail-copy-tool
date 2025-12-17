import os
import logging
import base64
import email
import hashlib
from datetime import datetime
from typing import Optional

import typer
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gmail_copy_tool.core.gmail_client import GmailClient
from gmail_copy_tool.utils.canonicalization import compute_canonical_hash
from gmail_copy_tool.utils.config import ConfigManager

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

def get_all_message_ids_with_headers(client, label=None, after=None, before=None):
    """Fetch all Message-IDs from the Gmail account."""
    service = client.service
    user_id = "me"
    message_ids = set()
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
            for msg in messages:
                msg_meta = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
                for header in msg_meta.get("payload", {}).get("headers", []):
                    if header.get("name", "").lower() == "message-id":
                        message_ids.add(header.get("value"))
                        break
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    return message_ids

@app.command()
def compare(
    source: str = typer.Argument(..., help="Source account nickname"),
    target: str = typer.Argument(..., help="Target account nickname"),
    label: str = typer.Option(None, help="Compare only emails with this Gmail label"),
    after: str = typer.Option(None, help="Compare emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Compare emails before this date (YYYY-MM-DD)"),
    year: int = typer.Option(None, help="Compare emails from specific year (e.g., 2024)")
):
    """Compare source and target accounts. Verifies all emails are copied (Message-ID based).
    
    Examples:
        gmail-copy-tool compare archive3 archive4
        gmail-copy-tool compare archive3 archive4 --year 2024
    """
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    logger = logging.getLogger(__name__)
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")
    if not debug_mode:
        logging.getLogger("gmail_copy_tool.core.gmail_client").setLevel(logging.WARNING)
    
    # Handle --year shortcut
    if year:
        after = f"{year}-01-01"
        before = f"{year}-12-31"
    
    # Resolve accounts from config
    config_manager = ConfigManager()
    
    try:
        source_account = config_manager.resolve_account(source)
        target_account = config_manager.resolve_account(target)
    except typer.Exit:
        raise
    
    source_email = source_account["email"]
    target_email = target_account["email"]
    source_creds = source_account["credentials"]
    target_creds = target_account["credentials"]
    source_token = source_account["token"]
    target_token = target_account["token"]
    
    if debug_mode:
        logger.debug(f"Source: {source_email}, Target: {target_email}")
        logger.debug(f"Credentials source: {source_creds}, Credentials target: {target_creds}")
    
    source_client = GmailClient(source_email, credentials_path=source_creds, token_path=source_token)
    target_client = GmailClient(target_email, credentials_path=target_creds, token_path=target_token)
    if debug_mode:
        logger.debug("Fetching all Message-IDs for source...")
    source_message_ids = get_all_message_ids_with_headers(source_client, label=label, after=after, before=before)
    if debug_mode:
        logger.debug(f"Source Message-IDs: {source_message_ids}")
        logger.debug("Fetching all Message-IDs for target...")
    target_message_ids = get_all_message_ids_with_headers(target_client, label=label, after=after, before=before)
    if debug_mode:
        logger.debug(f"Target Message-IDs: {target_message_ids}")
    missing_in_target = source_message_ids - target_message_ids
    extra_in_target = target_message_ids - source_message_ids
    if debug_mode:
        logger.debug(f"Missing in target: {missing_in_target}")
        logger.debug(f"Extra in target: {extra_in_target}")
    console = Console(force_terminal=True)
    summary_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=True)
    summary_table.add_column("Metric", style="bold", justify="right")
    summary_table.add_column("Value", style="bold green", justify="left")
    summary_table.add_row("Total in source", str(len(source_message_ids)))
    summary_table.add_row("Total in target", str(len(target_message_ids)))
    summary_table.add_row("Missing in target", str(len(missing_in_target)))
    summary_table.add_row("Extra in target", str(len(extra_in_target)))
    console.print(Panel(summary_table, title="📊 Comparison Summary", border_style="cyan", padding=(1,2)))
    if missing_in_target:
        if debug_mode:
            logger.debug("Building missing in target table...")
        table = Table(show_header=True, header_style="bold red", show_lines=True, box=SIMPLE)
        table.add_column("Message-ID", style="dim")
        for msg_id in list(missing_in_target)[:10]:
            table.add_row(msg_id)
        console.print(Panel(table, title="Missing in Target (sample)", border_style="red", padding=(1,2)))
    if extra_in_target:
        if debug_mode:
            logger.debug("Building extra in target table...")
        table = Table(show_header=True, header_style="bold yellow", show_lines=True, box=SIMPLE)
        table.add_column("Message-ID", style="dim")
        for msg_id in list(extra_in_target)[:10]:
            table.add_row(msg_id)
        console.print(Panel(table, title="Extra in Target (sample)", border_style="yellow", padding=(1,2)))