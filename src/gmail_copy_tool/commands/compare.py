import os
import logging
import time
from datetime import datetime

import typer
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from gmail_copy_tool.core.gmail_client import GmailClient
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
    """Fetch all messages and create fingerprints (message_id+subject+from+attachments) for comparison."""
    service = client.service
    user_id = "me"
    # Dict[fingerprint_key, List[email_metadata]]
    # fingerprint_key: computed from message_id+subject+from+attachments (Message-ID preserved during copy)
    # email_metadata: {subject, from, date, gmail_id, message_id, attachments} stored for API operations
    message_data = {}
    total_emails = 0  # Track total number of emails (including duplicates)
    duplicate_count = 0  # Track how many duplicates we found
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
    
    # Helper function to extract attachments (moved outside loop for reuse)
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
    
    # Helper function to process a single message metadata
    def process_message_metadata(msg_meta, gmail_id):
        """Process message metadata and return fingerprint data"""
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
        attachments = extract_attachments(parts)
        
        # Create fingerprint: subject + from + date_prefix + attachment_summary
        # Use only first 20 chars of date to handle slight time variations
        date_prefix = date_str[:20] if date_str else ""
        attachment_summary = "|".join(sorted([f"{a['filename']}:{a['size']}" for a in attachments]))
        fingerprint = f"{subject}||{from_addr}||{date_prefix}||{attachment_summary}"
        
        # DEBUG: Log fingerprint components for troubleshooting
        logger.debug(f"Fingerprint computed for gmail_id={gmail_id}")
        logger.debug(f"  Subject: {subject[:60]}")
        logger.debug(f"  From: {from_addr[:60]}")
        logger.debug(f"  Date prefix: '{date_prefix}'")
        logger.debug(f"  Attachments: {attachment_summary[:100]}")
        logger.debug(f"  Fingerprint: {fingerprint[:150]}...")
        
        return {
            "subject": subject,
            "from": from_addr,
            "date": date_str,
            "gmail_id": gmail_id,
            "message_id": msg_id,
            "attachments": attachments,
            "fingerprint": fingerprint
        }
    
    # First, collect all message IDs
    all_message_ids = []
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
            all_message_ids.extend(msg["id"] for msg in messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    
    # Now fetch metadata in batches of 20 (avoid "too many concurrent requests")
    BATCH_SIZE = 20
    total_messages = len(all_message_ids)
    logger.info(f"Fetching metadata for {total_messages} messages in batches of {BATCH_SIZE}...")
    
    # Import Console for progress bar (should be at top, but keeping changes minimal)
    from rich.console import Console
    console = Console(force_terminal=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        TextColumn("|"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching email metadata...", total=total_messages)
        
        for i in range(0, total_messages, BATCH_SIZE):
            batch_ids = all_message_ids[i:i + BATCH_SIZE]
            batch = service.new_batch_http_request()
            
            # Store results from batch
            batch_results = {}
            
            def create_callback(msg_id):
                """Create a callback function for this specific message ID"""
                def callback(request_id, response, exception):
                    if exception is not None:
                        logger.warning(f"Error fetching message {msg_id}: {exception}")
                    else:
                        batch_results[msg_id] = response
                return callback
            
            # Add all requests to the batch
            for msg_id in batch_ids:
                batch.add(
                    service.users().messages().get(userId=user_id, id=msg_id, format="metadata"),
                    callback=create_callback(msg_id)
                )
            
            # Execute the batch with retry logic for all errors
            max_retries = 5
            retry_delay = 2
            for attempt in range(max_retries):
                try:
                    batch.execute()
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        error_str = str(e)
                        # Check if it's a rate limit error (needs longer delay)
                        if "429" in error_str or "503" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                            logger.warning(f"Rate limit hit, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff for rate limits
                        else:
                            # Network or other transient errors - shorter retry delay
                            logger.warning(f"Batch failed ({e}), retrying in 3s... ({attempt + 1}/{max_retries})")
                            time.sleep(3)
                        continue
                    else:
                        # Final attempt failed
                        logger.error(f"Batch execution failed after {max_retries} attempts: {e}")
                        break
            
            # Process batch results
            for msg_id, msg_meta in batch_results.items():
                try:
                    data = process_message_metadata(msg_meta, msg_id)
                    total_emails += 1
                    fingerprint = data["fingerprint"]
                    if fingerprint in message_data:
                        duplicate_count += 1
                        logger.debug(f"Duplicate found: {data['subject'][:50]}")
                        message_data[fingerprint].append(data)
                    else:
                        message_data[fingerprint] = [data]
                except Exception as e:
                    logger.warning(f"Error processing message {msg_id}: {e}")
                    continue
            
            # Update progress bar
            processed = min(i + BATCH_SIZE, total_messages)
            progress.update(task, completed=processed)
            
            # Add 1 second delay between batches to avoid rate limits
            if i + BATCH_SIZE < total_messages:
                time.sleep(1.0)
    
    logger.info(f"Total emails fetched: {total_emails}, Unique fingerprints: {len(message_data)}, Duplicates: {duplicate_count}")
    return message_data, total_emails, duplicate_count

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
    sync: bool = typer.Option(False, help="Interactive mode: copy missing emails and ask to delete extras"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm all prompts (non-interactive mode)")
):
    """Compare source and target accounts using content-based fingerprint (message_id+subject+from+attachments).
    
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
    
    # Track timing for each phase
    timings = {}
    
    if debug_mode:
        logger.debug("Fetching all Message-IDs for source...")
    logger.info(f"Fetching messages from SOURCE: {source_email}")
    start_time = time.time()
    source_message_data, source_total, source_dupes = get_all_message_ids_with_headers(source_client, label=label, after=after, before=before)
    timings['source_fetch'] = time.time() - start_time
    logger.info(f"SOURCE fetch complete: {source_total} emails ({len(source_message_data)} unique, {source_dupes} duplicates) (took {timings['source_fetch']:.1f}s)")
    
    if debug_mode:
        logger.debug(f"Source has {len(source_message_data)} messages")
        logger.debug("Fetching all Message-IDs for target...")
    logger.info(f"Fetching messages from TARGET: {target_email}")
    start_time = time.time()
    target_message_data, target_total, target_dupes = get_all_message_ids_with_headers(target_client, label=label, after=after, before=before)
    timings['target_fetch'] = time.time() - start_time
    logger.info(f"TARGET fetch complete: {target_total} emails ({len(target_message_data)} unique, {target_dupes} duplicates) (took {timings['target_fetch']:.1f}s)")
    
    if debug_mode:
        logger.debug(f"Target has {len(target_message_data)} messages")
    
    source_msgids = set(source_message_data.keys())
    target_msgids = set(target_message_data.keys())
    
    missing_in_target = source_msgids - target_msgids
    extra_in_target = target_msgids - source_msgids
    
    # DEBUG: Collect analysis of missing emails to print at the end
    debug_analysis = []
    if debug_mode and missing_in_target:
        debug_analysis.append("=" * 80)
        debug_analysis.append("DETAILED ANALYSIS OF MISSING EMAILS:")
        debug_analysis.append("=" * 80)
        for i, fp in enumerate(list(missing_in_target)[:5], 1):
            emails = source_message_data[fp]
            first_email = emails[0]
            debug_analysis.append(f"\nMissing #{i}:")
            debug_analysis.append(f"  Fingerprint: {fp[:200]}")
            debug_analysis.append(f"  Subject: {first_email['subject'][:80]}")
            debug_analysis.append(f"  From: {first_email['from'][:80]}")
            debug_analysis.append(f"  Date: {first_email['date'][:30]}")
            debug_analysis.append(f"  Date prefix (fingerprint): '{first_email['date'][:20]}'")
            debug_analysis.append(f"  Message-ID: {first_email.get('message_id', 'N/A')[:60]}")
            debug_analysis.append(f"  Gmail ID (source): {first_email['gmail_id']}")
            debug_analysis.append(f"  Attachments: {len(first_email['attachments'])} files")
            if first_email['attachments']:
                for att in first_email['attachments'][:3]:
                    debug_analysis.append(f"    - {att['filename']} ({att['size']} bytes)")
            # Check if similar fingerprint exists in target
            similar_count = sum(1 for t_fp in target_msgids if t_fp[:100] == fp[:100])
            if similar_count > 0:
                debug_analysis.append(f"  ⚠ WARNING: {similar_count} fingerprints in TARGET start with same 100 chars!")
        debug_analysis.append("=" * 80)
    
    # For display and copying, use the first email of each fingerprint
    source_message_display = {fp: emails[0] for fp, emails in source_message_data.items()}
    target_message_display = {fp: emails[0] for fp, emails in target_message_data.items()}
    
    logger.info(f"Comparison results (CONTENT-BASED): MISSING_IN_TARGET={len(missing_in_target)}, EXTRA_IN_TARGET={len(extra_in_target)}")
    logger.info(f"Using fingerprint: Message-ID + Subject + From + Attachments")
    
    if debug_mode:
        logger.debug(f"Missing in target: {len(missing_in_target)}")
        logger.debug(f"Extra in target: {len(extra_in_target)}")
    console = Console(force_terminal=True)
    summary_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=True)
    summary_table.add_column("Metric", style="bold", justify="right")
    summary_table.add_column("Value", style="bold green", justify="left")
    summary_table.add_row("Total emails in source", f"{source_total} ({len(source_msgids)} unique)")
    summary_table.add_row("Total emails in target", f"{target_total} ({len(target_msgids)} unique)")
    if source_dupes > 0:
        summary_table.add_row("Duplicates in source", str(source_dupes), style="yellow")
    if target_dupes > 0:
        summary_table.add_row("Duplicates in target", str(target_dupes), style="yellow")
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
            data = source_message_data[fingerprint][0]  # Use first email from list
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
            data = target_message_data[fingerprint][0]  # Use first email from list
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
        
        if yes:
            logger.info("Auto-confirm mode enabled (--yes flag)")
            console.print("[bold green]Auto-confirm enabled: proceeding with sync...[/bold green]\n")
        elif not typer.confirm(f"Do you want to proceed with modifying {target_email}?", default=False):
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
            console.print(f"\n[bold green]📧 COPYING MISSING EMAILS TO TARGET: {len(missing_in_target)} emails[/bold green]")
            console.print(f"[cyan]Copying from {source_email} to {target_email}[/cyan]\n")
            
            sorted_missing = sorted(missing_in_target)
            logger.debug(f"First 5 fingerprints to copy: {[fp[:80] for fp in sorted_missing[:5]]}")
            
            copy_start = time.time()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
                TextColumn("|"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Copying emails...", total=len(sorted_missing))
                
                for i, fingerprint in enumerate(sorted_missing, 1):
                    data = source_message_data[fingerprint][0]  # Use first email from list
                    
                    # Update progress description with current email subject
                    subject_preview = data['subject'][:45] + '...' if len(data['subject']) > 45 else data['subject']
                    progress.update(task, description=f"[cyan]{subject_preview}")
                    
                    logger.info(f"[{i}/{len(missing_in_target)}] Copying fingerprint: {fingerprint[:80]}...")
                    logger.info(f"  Message-ID: {data.get('message_id', 'N/A')[:50]}")
                    
                    # DEBUG: Log details of email being copied
                    if debug_mode:
                        logger.debug(f"COPY OPERATION #{i}:")
                        logger.debug(f"  Source gmail_id: {data['gmail_id']}")
                        logger.debug(f"  Subject: {data['subject'][:100]}")
                        logger.debug(f"  From: {data['from'][:100]}")
                        logger.debug(f"  Date: {data['date'][:30]}")
                        logger.debug(f"  Date prefix in fingerprint: '{data['date'][:20]}'")
                        logger.debug(f"  Fingerprint being copied: {fingerprint[:200]}")
                    
                    # Get the full email from source and copy to target
                    try:
                        logger.debug(f"Fetching raw email from SOURCE, gmail_id={data['gmail_id']}")
                        source_msg = source_client.service.users().messages().get(
                            userId="me", id=data['gmail_id'], format="raw"
                        ).execute()
                        raw_email = source_msg.get('raw', '')
                        
                        if not raw_email:
                            logger.error(f"FAILED: No raw email data for gmail_id={data['gmail_id']}")
                            copy_errors.append(f"No content: {fingerprint[:50]}")
                            progress.advance(task)
                            continue
                        
                        logger.debug(f"Raw email size: {len(raw_email)} chars")
                        logger.debug(f"Inserting into TARGET account {target_email}")
                        
                        # Insert into target
                        result = target_client.service.users().messages().insert(
                            userId="me", body={"raw": raw_email}, internalDateSource="dateHeader"
                        ).execute()
                        
                        new_gmail_id = result.get('id', 'unknown')
                        logger.info(f"SUCCESS: Copied to TARGET, new gmail_id={new_gmail_id}")
                        
                        # DEBUG: Verify what fingerprint the copied email will have in next sync
                        if debug_mode:
                            logger.debug(f"  Email copied successfully")
                            logger.debug(f"  New TARGET gmail_id: {new_gmail_id}")
                            logger.debug(f"  Original fingerprint: {fingerprint[:200]}")
                            logger.debug(f"  Next sync should find this email in TARGET with SAME fingerprint")
                        
                        copied_count += 1
                        
                    except Exception as e:
                        logger.error(f"FAILED to copy: {e}", exc_info=True)
                        copy_errors.append(f"{fingerprint[:50]}: {str(e)}")
                    
                    progress.advance(task)
            
            timings['copy_phase'] = time.time() - copy_start
            logger.info(f"Copy phase complete (took {timings['copy_phase']:.1f}s)")
        else:
            timings['copy_phase'] = 0
        
        # Process extra emails - ask user to delete from target
        if extra_in_target:
            delete_start = time.time()
            logger.info(f"Starting delete phase: {len(extra_in_target)} extra emails in target")
            console.print(f"\n[bold yellow]🗑 DELETING EXTRA EMAILS FROM TARGET: {len(extra_in_target)} emails not in source[/bold yellow]")
            console.print(f"[red]These emails exist in {target_email} but NOT in {source_email}[/red]\n")
            
            delete_all = False
            sorted_extra = sorted(extra_in_target)
            logger.debug(f"First 5 fingerprints to potentially delete: {[fp[:80] for fp in sorted_extra[:5]]}")
            
            for i, fingerprint in enumerate(sorted_extra, 1):
                data = target_message_data[fingerprint][0]  # Use first email from list
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
                elif yes:
                    delete = True
                    delete_all = True  # Set delete_all for remaining emails
                    logger.info("Auto-confirm mode: deleting all extra emails")
                    console.print(f"[red]→ Deleting (auto-confirm mode)[/red]")
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
            
            timings['delete_phase'] = time.time() - delete_start
            logger.info(f"Delete phase complete (took {timings['delete_phase']:.1f}s)")
        else:
            timings['delete_phase'] = 0
        
        # Cleanup duplicates in target (keep only first occurrence of each fingerprint)
        duplicates_to_remove = []
        for fingerprint, emails in target_message_data.items():
            if len(emails) > 1:
                # Keep first email, mark rest for deletion
                for email in emails[1:]:
                    duplicates_to_remove.append(email)
        
        if duplicates_to_remove:
            logger.info(f"Starting duplicate cleanup: {len(duplicates_to_remove)} duplicate emails in target")
            console.print(f"\n[bold yellow]🧹 REMOVING DUPLICATES FROM TARGET: {len(duplicates_to_remove)} duplicate emails[/bold yellow]")
            console.print(f"[cyan]Keeping oldest copy of each email[/cyan]\n")
            
            cleanup_start = time.time()
            cleaned_count = 0
            cleanup_errors = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
                TextColumn("|"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[yellow]Removing duplicates...", total=len(duplicates_to_remove))
                
                for email in duplicates_to_remove:
                    subject_preview = email['subject'][:45] + '...' if len(email['subject']) > 45 else email['subject']
                    progress.update(task, description=f"[yellow]Removing: {subject_preview}")
                    
                    try:
                        logger.debug(f"Deleting duplicate from TARGET, gmail_id={email['gmail_id']}")
                        target_client.service.users().messages().delete(
                            userId="me", id=email['gmail_id']
                        ).execute()
                        logger.info(f"SUCCESS: Deleted duplicate gmail_id={email['gmail_id']}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"FAILED to delete duplicate gmail_id={email['gmail_id']}: {e}", exc_info=True)
                        cleanup_errors.append(f"{email['subject'][:50]}: {str(e)}")
                    
                    progress.advance(task)
            
            timings['cleanup_phase'] = time.time() - cleanup_start
            logger.info(f"Cleanup phase complete: removed {cleaned_count} duplicates (took {timings['cleanup_phase']:.1f}s)")
        else:
            timings['cleanup_phase'] = 0
            logger.info("No duplicates found in target")
        
        # Calculate total time
        timings['total'] = sum(timings.values())
        
        # Summary
        logger.info("SYNC COMPLETE")
        logger.info(f"Results: COPIED={copied_count}, DELETED={deleted_count}, CLEANED_DUPLICATES={cleaned_count if duplicates_to_remove else 0}, SKIPPED={skipped_count}")
        logger.info(f"Errors: COPY_ERRORS={len(copy_errors)}, DELETE_ERRORS={len(delete_errors)}")
        
        console.print("\n[bold cyan]" + "═" * 70 + "[/bold cyan]")
        console.print("[bold cyan]                    SYNC COMPLETE[/bold cyan]")
        console.print("[bold cyan]" + "═" * 70 + "[/bold cyan]\n")
        console.print(f"[green]✓ Emails copied to {target_email}: {copied_count}[/green]")
        console.print(f"[red]✓ Emails permanently deleted from {target_email}: {deleted_count}[/red]")
        if duplicates_to_remove:
            console.print(f"[yellow]✓ Duplicate emails removed from {target_email}: {cleaned_count}[/yellow]")
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
        
        # Timing summary
        console.print(f"\n[bold cyan]⏱ Performance Summary:[/bold cyan]")
        timing_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
        timing_table.add_column("Phase", style="cyan", justify="left")
        timing_table.add_column("Time", style="green", justify="right")
        timing_table.add_row("Fetch source emails", f"{timings['source_fetch']:.1f}s")
        timing_table.add_row("Fetch target emails", f"{timings['target_fetch']:.1f}s")
        if timings['copy_phase'] > 0:
            timing_table.add_row(f"Copy {copied_count} emails", f"{timings['copy_phase']:.1f}s")
        if timings['delete_phase'] > 0:
            timing_table.add_row(f"Delete {deleted_count} emails", f"{timings['delete_phase']:.1f}s")
        if timings.get('cleanup_phase', 0) > 0:
            timing_table.add_row(f"Remove {cleaned_count} duplicates", f"{timings['cleanup_phase']:.1f}s")
        timing_table.add_row("[bold]TOTAL TIME[/bold]", f"[bold]{timings['total']:.1f}s[/bold]")
        console.print(timing_table)
        
        # Print debug analysis at the end if available
        if debug_analysis:
            console.print("\n[bold yellow]🔍 DEBUG: FINGERPRINT ANALYSIS[/bold yellow]")
            for line in debug_analysis:
                console.print(f"[dim]{line}[/dim]")
        
        console.print(f"\n[bold white]Run 'gmail-copy-tool sync {source} {target}' again to verify accounts are identical.[/bold white]")
        logger.info(f"Sync summary logged. Total time: {timings['total']:.1f}s")