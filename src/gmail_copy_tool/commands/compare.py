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
    """Fetch all messages and create fingerprints (subject+from+date+attachments) for comparison."""
    service = client.service
    user_id = "me"
    message_data = {}  # fingerprint -> {subject, from, date, gmail_id, message_id, attachments}
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
                headers = msg_meta.get("payload", {}).get("headers", [])
                msg_id = None
                subject = ""
                from_addr = ""
                date_str = ""
                
                for header in headers:
                    name = header.get("name", "").lower()
                    value = header.get("value", "")
                    if name == "message-id":
                        msg_id = value
                    elif name == "subject":
                        subject = value
                    elif name == "from":
                        from_addr = value
                    elif name == "date":
                        date_str = value
                
                # Get attachment info
                attachments = []
                payload = msg_meta.get('payload', {})
                parts = payload.get('parts', [])
                
                def extract_attachments(parts_list):
                    """Recursively extract attachment filenames and sizes"""
                    att_list = []
                    for part in parts_list:
                        if part.get('filename'):
                            att_list.append({
                                'filename': part.get('filename'),
                                'size': part.get('body', {}).get('size', 0)
                            })
                        if part.get('parts'):
                            att_list.extend(extract_attachments(part.get('parts')))
                    return att_list
                
                attachments = extract_attachments(parts)
                
                # Create fingerprint: subject + from + date_prefix + attachment_summary
                # Use only first 20 chars of date to handle slight time variations
                date_prefix = date_str[:20] if date_str else ""
                attachment_summary = "|".join(sorted([f"{a['filename']}:{a['size']}" for a in attachments]))
                fingerprint = f"{subject}||{from_addr}||{date_prefix}||{attachment_summary}"
                
                message_data[fingerprint] = {
                    "subject": subject,
                    "from": from_addr,
                    "date": date_str,
                    "gmail_id": msg["id"],
                    "message_id": msg_id,
                    "attachments": attachments,
                    "fingerprint": fingerprint
                }
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    return message_data

@app.command()
def compare(
    source: str = typer.Argument(..., help="Source account nickname"),
    target: str = typer.Argument(..., help="Target account nickname"),
    label: str = typer.Option(None, help="Compare only emails with this Gmail label"),
    after: str = typer.Option(None, help="Compare emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Compare emails before this date (YYYY-MM-DD)"),
    year: int = typer.Option(None, help="Compare emails from specific year (e.g., 2024)"),
    limit: int = typer.Option(20, help="Maximum number of differences to show (default: 20)"),
    show_duplicates: bool = typer.Option(False, help="Show detailed duplicate analysis using content hash"),
    sync: bool = typer.Option(False, help="Interactive mode: copy missing emails and ask to delete extras")
):
    """Compare source and target accounts using content-based fingerprint (subject+from+date+attachments).
    
    Examples:
        gmail-copy-tool sync archive3 archive4
        gmail-copy-tool sync archive3 archive4 --year 2024
        gmail-copy-tool sync archive3 archive4 --limit 5 --show-duplicates
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
    
    logger.info(f"Starting comparison: SOURCE={source_email}, TARGET={target_email}")
    
    if debug_mode:
        logger.debug("Fetching all Message-IDs for source...")
    logger.info(f"Fetching messages from SOURCE: {source_email}")
    source_message_data = get_all_message_ids_with_headers(source_client, label=label, after=after, before=before)
    logger.info(f"SOURCE fetch complete: {len(source_message_data)} messages found")
    
    if debug_mode:
        logger.debug(f"Source has {len(source_message_data)} messages")
        logger.debug("Fetching all Message-IDs for target...")
    logger.info(f"Fetching messages from TARGET: {target_email}")
    target_message_data = get_all_message_ids_with_headers(target_client, label=label, after=after, before=before)
    logger.info(f"TARGET fetch complete: {len(target_message_data)} messages found")
    
    if debug_mode:
        logger.debug(f"Target has {len(target_message_data)} messages")
    
    source_msgids = set(source_message_data.keys())
    target_msgids = set(target_message_data.keys())
    
    missing_in_target = source_msgids - target_msgids
    extra_in_target = target_msgids - source_msgids
    
    logger.info(f"Comparison results (CONTENT-BASED): MISSING_IN_TARGET={len(missing_in_target)}, EXTRA_IN_TARGET={len(extra_in_target)}")
    logger.info(f"Using fingerprint: Subject + From + Date(first 20 chars) + Attachments")
    
    if debug_mode:
        logger.debug(f"Missing in target: {len(missing_in_target)}")
        logger.debug(f"Extra in target: {len(extra_in_target)}")
    console = Console(force_terminal=True)
    summary_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=True)
    summary_table.add_column("Metric", style="bold", justify="right")
    summary_table.add_column("Value", style="bold green", justify="left")
    summary_table.add_row("Total in source", str(len(source_msgids)))
    summary_table.add_row("Total in target", str(len(target_msgids)))
    summary_table.add_row("Missing in target", str(len(missing_in_target)))
    summary_table.add_row("Extra in target", str(len(extra_in_target)))
    console.print(Panel(summary_table, title="📊 Comparison Summary", border_style="cyan", padding=(1,2)))
    
    # Helper to find potential duplicates by subject/from/date
    def find_similar_in_target(source_data, target_data_dict):
        """Check if email might exist in target with different Message-ID"""
        subject = source_data.get("subject", "").strip().lower()
        from_addr = source_data.get("from", "").strip().lower()
        date = source_data.get("date", "")[:20].strip()  # First 20 chars of date
        
        for target_msgid, target_data in target_data_dict.items():
            target_subject = target_data.get("subject", "").strip().lower()
            target_from = target_data.get("from", "").strip().lower()
            target_date = target_data.get("date", "")[:20].strip()
            
            # Match if subject AND from are the same (date can vary slightly)
            if subject and subject == target_subject and from_addr == target_from:
                return target_msgid, target_data
        return None, None
    
    if missing_in_target:
        if debug_mode:
            logger.debug("Building missing in target table...")
        table = Table(show_header=True, header_style="bold red", show_lines=True, box=SIMPLE)
        table.add_column("#", style="dim", width=3)
        table.add_column("Date", style="cyan", width=20)
        table.add_column("From", style="yellow", width=30)
        table.add_column("Subject", style="white", width=40)
        table.add_column("Attachments", style="green", width=15)
        if show_duplicates:
            table.add_column("Possible Duplicate?", style="magenta", width=20)
        
        count = 0
        for fingerprint in list(missing_in_target)[:limit]:
            count += 1
            data = source_message_data[fingerprint]
            # Truncate long fields
            date_display = data["date"][:20] if data["date"] else ""
            from_display = data["from"][:30] if data["from"] else ""
            subject_display = data["subject"][:40] if data["subject"] else "(no subject)"
            att_count = len(data["attachments"])
            att_display = f"{att_count} file(s)" if att_count > 0 else "None"
            
            row_data = [str(count), date_display, from_display, subject_display, att_display]
            
            if show_duplicates:
                similar_fp, similar_data = find_similar_in_target(data, target_message_data)
                if similar_fp:
                    row_data.append("⚠ YES (diff Msg-ID)")
                else:
                    row_data.append("No")
            
            table.add_row(*row_data)
        
        title = f"❌ Missing in Target ({len(missing_in_target)} total, showing {min(limit, len(missing_in_target))})"
        console.print(Panel(table, title=title, border_style="red", padding=(1,2)))
        
        if len(missing_in_target) > limit:
            console.print(f"[yellow]... and {len(missing_in_target) - limit} more. Use --limit to show more.[/yellow]\n")
    
    if extra_in_target:
        if debug_mode:
            logger.debug("Building extra in target table...")
        table = Table(show_header=True, header_style="bold yellow", show_lines=True, box=SIMPLE)
        table.add_column("#", style="dim", width=3)
        table.add_column("Date", style="cyan", width=20)
        table.add_column("From", style="yellow", width=30)
        table.add_column("Subject", style="white", width=40)
        table.add_column("Attachments", style="green", width=15)
        
        count = 0
        for fingerprint in list(extra_in_target)[:limit]:
            count += 1
            data = target_message_data[fingerprint]
            # Truncate long fields
            date_display = data["date"][:20] if data["date"] else ""
            from_display = data["from"][:30] if data["from"] else ""
            subject_display = data["subject"][:40] if data["subject"] else "(no subject)"
            att_count = len(data["attachments"])
            att_display = f"{att_count} file(s)" if att_count > 0 else "None"
            table.add_row(str(count), date_display, from_display, subject_display, att_display)
        
        title = f"➕ Extra in Target ({len(extra_in_target)} total, showing {min(limit, len(extra_in_target))})"
        console.print(Panel(table, title=title, border_style="yellow", padding=(1,2)))
        
        if len(extra_in_target) > limit:
            console.print(f"[yellow]... and {len(extra_in_target) - limit} more. Use --limit to show more.[/yellow]\n")
    
    # Interactive sync mode
    if sync:
        logger.info("SYNC MODE STARTED")
        console.print("\n[bold cyan]" + "═" * 70 + "[/bold cyan]")
        console.print("[bold cyan]               SYNCHRONIZATION MODE - INTERACTIVE[/bold cyan]")
        console.print("[bold cyan]" + "═" * 70 + "[/bold cyan]\n")
        
        console.print(f"[bold white]SOURCE (READ-ONLY):[/bold white]  {source_email}")
        console.print(f"[bold yellow]TARGET (WILL BE MODIFIED):[/bold yellow] {target_email}\n")
        
        logger.info(f"SOURCE={source_email} (read-only), TARGET={target_email} (will be modified)")
        logger.info(f"Will copy {len(missing_in_target)} emails TO target")
        logger.info(f"Will ask to delete {len(extra_in_target)} emails FROM target")
        
        console.print("[bold red]⚠ IMPORTANT:[/bold red]")
        console.print(f"  • [green]{source_email}[/green] will NOT be touched (read-only)")
        console.print(f"  • [yellow]{target_email}[/yellow] will be modified to become identical to source")
        console.print(f"  • Missing emails will be COPIED from source to target")
        console.print(f"  • Extra emails in target will be PERMANENTLY DELETED (cannot be recovered)\n")
        
        if not typer.confirm(f"Do you want to proceed with modifying {target_email}?", default=False):
            logger.info("User cancelled sync operation")
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        
        logger.info("User confirmed - proceeding with sync")
        copied_count = 0
        deleted_count = 0
        skipped_count = 0
        copy_errors = []
        delete_errors = []
        
        # Process missing emails - copy to target
        if missing_in_target:
            logger.info(f"Starting copy phase: {len(missing_in_target)} emails to copy")
            console.print(f"\n[bold red]📥 COPYING MISSING EMAILS TO TARGET: {len(missing_in_target)} emails[/bold red]")
            
            sorted_missing = sorted(missing_in_target)
            logger.debug(f"First 5 fingerprints to copy: {[fp[:80] for fp in sorted_missing[:5]]}")
            
            for i, fingerprint in enumerate(sorted_missing, 1):
                data = source_message_data[fingerprint]
                logger.info(f"[{i}/{len(missing_in_target)}] Copying fingerprint: {fingerprint[:80]}...")
                logger.info(f"  Message-ID: {data.get('message_id', 'N/A')[:50]}")
                
                console.print(f"\n[cyan]Email {i}/{len(missing_in_target)}:[/cyan]")
                console.print(f"  Date: {data['date'][:40]}")
                console.print(f"  From: {data['from'][:60]}")
                console.print(f"  Subject: {data['subject'][:80]}")
                console.print(f"  Attachments: {len(data['attachments'])} file(s)")
                console.print(f"  Gmail ID (source): {data['gmail_id']}")
                console.print(f"  Message-ID: {data.get('message_id', 'N/A')[:60]}")
                
                # Get the full email from source and copy to target
                try:
                    logger.debug(f"Fetching raw email from SOURCE, gmail_id={data['gmail_id']}")
                    source_msg = source_client.service.users().messages().get(
                        userId="me", id=data['gmail_id'], format="raw"
                    ).execute()
                    raw_email = source_msg.get('raw', '')
                    
                    if not raw_email:
                        logger.error(f"FAILED: No raw email data for gmail_id={data['gmail_id']}")
                        console.print(f"[red]✗ Failed: No email content received[/red]")
                        copy_errors.append(f"No content: {fingerprint[:50]}")
                        continue
                    
                    logger.debug(f"Raw email size: {len(raw_email)} chars")
                    logger.debug(f"Inserting into TARGET account {target_email}")
                    
                    # Insert into target
                    result = target_client.service.users().messages().insert(
                        userId="me", body={"raw": raw_email}, internalDateSource="dateHeader"
                    ).execute()
                    
                    new_gmail_id = result.get('id', 'unknown')
                    logger.info(f"SUCCESS: Copied to TARGET, new gmail_id={new_gmail_id}")
                    console.print(f"[green]✓ Copied to {target_email} (new ID: {new_gmail_id})[/green]")
                    copied_count += 1
                    
                except Exception as e:
                    logger.error(f"FAILED to copy: {e}", exc_info=True)
                    console.print(f"[red]✗ Failed to copy: {e}[/red]")
                    copy_errors.append(f"{fingerprint[:50]}: {str(e)}")
        
        # Process extra emails - ask user to delete from target
        if extra_in_target:
            logger.info(f"Starting delete phase: {len(extra_in_target)} extra emails in target")
            console.print(f"\n[bold yellow]🗑 DELETING EXTRA EMAILS FROM TARGET: {len(extra_in_target)} emails not in source[/bold yellow]")
            console.print(f"[red]These emails exist in {target_email} but NOT in {source_email}[/red]\n")
            
            delete_all = False
            sorted_extra = sorted(extra_in_target)
            logger.debug(f"First 5 fingerprints to potentially delete: {[fp[:80] for fp in sorted_extra[:5]]}")
            
            for i, fingerprint in enumerate(sorted_extra, 1):
                data = target_message_data[fingerprint]
                logger.info(f"[{i}/{len(extra_in_target)}] Extra email fingerprint: {fingerprint[:80]}...")
                logger.info(f"  Message-ID: {data.get('message_id', 'N/A')[:50]}")
                
                # No need to check for similar - we're using content-based comparison now
                # If it's in extra_in_target, it truly doesn't exist in source
                
                console.print(f"\n[yellow]Email {i}/{len(extra_in_target)} in {target_email}:[/yellow]")
                console.print(f"  Date: {data['date'][:40]}")
                console.print(f"  From: {data['from'][:60]}")
                console.print(f"  Subject: {data['subject'][:80]}")
                console.print(f"  Attachments: {len(data['attachments'])} file(s)")
                console.print(f"  Gmail ID (target): {data['gmail_id']}")
                console.print(f"  Message-ID: {data.get('message_id', 'N/A')[:60]}")
                console.print(f"  [red]This email does NOT exist in SOURCE (content-based check)[/red]")
                
                # Ask user (content-based means no false duplicates)
                delete = False
                if delete_all:
                    delete = True
                    logger.info("Delete ALL mode active - will delete without asking")
                    console.print(f"[red]→ Deleting (delete all mode)[/red]")
                else:
                    response = typer.prompt(
                        f"[red]PERMANENTLY DELETE[/red] from {target_email}? (y/n/a for all)",
                        type=str,
                        default="n"
                    ).lower().strip()
                    
                    logger.info(f"User response: '{response}'")
                    
                    if response == 'a':
                        delete_all = True
                        delete = True
                        logger.info("User selected DELETE ALL - will delete all remaining")
                        console.print(f"[red]→ Deleting this and all remaining emails[/red]")
                    elif response == 'y':
                        delete = True
                        logger.info("User confirmed deletion")
                    else:
                        delete = False
                        logger.info("User skipped deletion")
                
                if delete:
                    try:
                        logger.debug(f"Deleting from TARGET, gmail_id={data['gmail_id']}")
                        target_client.service.users().messages().delete(
                            userId="me", id=data['gmail_id']
                        ).execute()
                        logger.info(f"SUCCESS: Permanently deleted gmail_id={data['gmail_id']} from TARGET")
                        console.print(f"[green]✓ Permanently deleted from {target_email}[/green]")
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"FAILED to delete gmail_id={data['gmail_id']}: {e}", exc_info=True)
                        console.print(f"[red]✗ Failed to delete: {e}[/red]")
                        delete_errors.append(f"{fingerprint[:50]}: {str(e)}")
                else:
                    logger.info("Skipped deletion")
                    console.print(f"[dim]→ Skipped (kept in {target_email})[/dim]")
                    skipped_count += 1
        
        # Summary
        logger.info("SYNC COMPLETE")
        logger.info(f"Results: COPIED={copied_count}, DELETED={deleted_count}, SKIPPED={skipped_count}")
        logger.info(f"Errors: COPY_ERRORS={len(copy_errors)}, DELETE_ERRORS={len(delete_errors)}")
        
        console.print("\n[bold cyan]" + "═" * 70 + "[/bold cyan]")
        console.print("[bold cyan]                    SYNC COMPLETE[/bold cyan]")
        console.print("[bold cyan]" + "═" * 70 + "[/bold cyan]\n")
        console.print(f"[green]✓ Emails copied to {target_email}: {copied_count}[/green]")
        console.print(f"[red]✓ Emails permanently deleted from {target_email}: {deleted_count}[/red]")
        console.print(f"[dim]→ Deletions skipped (kept in {target_email}): {skipped_count}[/dim]")
        
        if copy_errors:
            console.print(f"\n[bold red]⚠ Copy errors ({len(copy_errors)}):[/bold red]")
            for err in copy_errors[:10]:
                console.print(f"  [red]• {err}[/red]")
            if len(copy_errors) > 10:
                console.print(f"  [dim]... and {len(copy_errors) - 10} more[/dim]")
                
        if delete_errors:
            console.print(f"\n[bold red]⚠ Delete errors ({len(delete_errors)}):[/bold red]")
            for err in delete_errors[:10]:
                console.print(f"  [red]• {err}[/red]")
            if len(delete_errors) > 10:
                console.print(f"  [dim]... and {len(delete_errors) - 10} more[/dim]")
        
        console.print(f"\n[bold white]Run 'compare {source} {target}' again to verify accounts are identical.[/bold white]")
        logger.info(f"Sync summary logged. Check logs for details.")