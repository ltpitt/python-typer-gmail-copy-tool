import logging
import os
import re
from datetime import datetime

import typer
from rich.align import Align
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()

logger = logging.getLogger(__name__)


def get_metadata(client, msg_id):
    try:
        msg = client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = "(No Subject)"
        date = "(No Date)"
        for h in headers:
            if h["name"].lower() == "subject":
                subject = h["value"]
            if h["name"].lower() == "date":
                date = h["value"]
        # Truncate subject for neatness
        if len(subject) > 40:
            subject = subject[:37] + "..."
        return subject, date
    except Exception:
        return "(Error fetching subject)", "(Error fetching date)"


@app.command()
def compare(
    source: str = typer.Option(..., help="Source Gmail account email address"),
    target: str = typer.Option(..., help="Target Gmail account email address"),
    credentials_source: str = typer.Option("credentials_source.json", help="Path to source account credentials file (default: credentials_source.json)"),
    credentials_target: str = typer.Option("credentials_target.json", help="Path to target account credentials file (default: credentials_target.json)"),
    label: str = typer.Option(None, help="Compare only emails with this Gmail label"),
    after: str = typer.Option(None, help="Compare emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Compare emails before this date (YYYY-MM-DD)")
):
    """Compare source and target Gmail accounts to verify all emails have been copied."""
    # Enable debug logging if GMAIL_COPY_TOOL_DEBUG=1
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")
    try:
        logger.info(f"[COMPARE] after={after} before={before} label={label}")
        source_client = GmailClient(source, credentials_path=credentials_source)
        target_client = GmailClient(target, credentials_path=credentials_target)

        # Fetch all message IDs from both accounts (with optional filters)
        source_ids_list = _get_all_message_ids(source_client, label=label, after=after, before=before)
        target_ids_list = _get_all_message_ids(target_client, label=label, after=after, before=before)
        logger.info(f"[COMPARE] Source message IDs: {source_ids_list}")
        logger.info(f"[COMPARE] Target message IDs: {target_ids_list}")
        source_ids = set(source_ids_list) if source_ids_list is not None else set()
        target_ids = set(target_ids_list) if target_ids_list is not None else set()
        if debug_mode:
            logger.debug(f"Source message IDs: {source_ids_list}")
            logger.debug(f"Target message IDs: {target_ids_list}")
            # Print metadata for each target message
            for msg_id in target_ids_list:
                try:
                    msg = target_client.service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
                    logger.debug(f"Target message {msg_id} metadata: {msg}")
                except Exception as e:
                    logger.error(f"Failed to fetch metadata for target message {msg_id}: {e}")

        missing_in_target = source_ids - target_ids
        extra_in_target = target_ids - source_ids

        console = Console()

        # --- Summary Table ---
        summary_table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=True)
        summary_table.add_column("Metric", style="bold", justify="right")
        summary_table.add_column("Value", style="bold green", justify="left")
        summary_table.add_row("Total in source", str(len(source_ids)))
        summary_table.add_row("Total in target", str(len(target_ids)))
        summary_table.add_row("Missing in target", str(len(missing_in_target)))
        summary_table.add_row("Extra in target", str(len(extra_in_target)))
        console.print(Panel(summary_table, title="📊 Comparison Summary", border_style="cyan", padding=(1,2)))

        # --- Missing in Target ---
        if missing_in_target:
            table = Table(show_header=True, header_style="bold red", show_lines=True, box=SIMPLE)
            table.add_column("ID", style="dim")
            table.add_column("Subject")
            table.add_column("Date")
            for msg_id in list(missing_in_target)[:20]:
                subject, date = get_metadata(source_client, msg_id)
                table.add_row(msg_id, subject, date)
            panel_title = "6d1  Messages missing in targets"  # Add space after emoji
            missing_panel = Panel(table, border_style="red", padding=(0,2), title=panel_title)
            console.print(missing_panel)
            if len(missing_in_target) > 20:
                console.print(Text(f"...and {len(missing_in_target) - 20} more.", style="italic red"))
            # Add plain text line for test parsing
            print("Missing IDs:", " ".join(list(missing_in_target)))
        else:
            found_panel = Panel(Text("197 All source messages found in target.", style="bold green"), border_style="green", padding=(0,2), title="")
            console.print(found_panel)

        # --- Extra in Target ---
        if extra_in_target:
            table = Table(show_header=True, header_style="bold yellow", show_lines=True, box=SIMPLE)
            table.add_column("ID", style="dim")
            table.add_column("Subject")
            table.add_column("Date")
            for msg_id in list(extra_in_target)[:20]:
                subject, date = get_metadata(target_client, msg_id)
                table.add_row(msg_id, subject, date)
            panel_title = "⚠️  Messages in target not found in source"  
            extra_panel = Panel(table, border_style="yellow", padding=(0,2), title=panel_title)
            console.print(extra_panel)
            if len(extra_in_target) > 20:
                console.print(Text(f"...and {len(extra_in_target) - 20} more.", style="italic yellow"))
            # Add plain text line for test parsing
            print("Extra IDs:", " ".join(list(extra_in_target)))
        else:
            no_extra_panel = Panel(Text("✅ No extra messages in target.", style="bold green"), border_style="green", padding=(0,2), title="")
            console.print(no_extra_panel)

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
    except Exception as e:
        logger.exception(f"Error during compare: {e}")
        typer.secho(f"ERROR: {str(e)} (credentials issue or other error)", fg=typer.colors.RED, bold=True)
        import sys; sys.stdout.flush(); sys.stderr.flush()


def normalize_date(date_str):
    if not date_str:
        return None
    # Accept YYYY-MM-DD, YYYY/MM/DD, or RFC 2822, output YYYY/MM/DD
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


def _get_all_message_ids(client, label=None, after=None, before=None):
    """Fetch all message IDs from a GmailClient with optional filters."""
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
    logger.info(f"[_get_all_message_ids] Query: '{query.strip()}', label_ids={label_ids}")
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
    logger.info(f"[_get_all_message_ids] Found {len(message_ids)} message IDs: {message_ids}")
    return message_ids
