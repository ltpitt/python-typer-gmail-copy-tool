
import typer
from typing import Optional
from gmail_copy_tool.core.gmail_client import GmailClient
from gmail_copy_tool.utils.config import ConfigManager

app = typer.Typer()

@app.command()
def analyze(
    account: str = typer.Argument(..., help="Account nickname"),
    after: str = typer.Option(None, help="Count emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Count emails before this date (YYYY-MM-DD)"),
    label: str = typer.Option(None, help="Count emails with this Gmail label"),
    year: int = typer.Option(None, help="Count emails from specific year (e.g., 2024)")
):
    """Count emails in a Gmail account. Supports filters by date and label.
    
    Examples:
        gmail-copy-tool analyze archive3
        gmail-copy-tool analyze archive3 --year 2024
        gmail-copy-tool analyze archive3 --label "Work"
    """
    import os, logging
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    if not debug_mode:
        logging.getLogger("gmail_copy_tool.core.gmail_client").setLevel(logging.WARNING)
    
    # Handle --year shortcut
    if year:
        after = f"{year}-01-01"
        before = f"{year}-12-31"
    
    # Resolve account from config
    config_manager = ConfigManager()
    
    try:
        account_info = config_manager.resolve_account(account)
    except typer.Exit:
        raise
    
    account_email = account_info["email"]
    account_creds = account_info["credentials"]
    account_token = account_info["token"]
    
    try:
        client = GmailClient(account_email, credentials_path=account_creds, token_path=account_token)
        typer.echo(f"Analyzing account: {account_email}")
        count = client.count_emails(after=after, before=before, label=label)
        typer.echo(f"Total emails: {count}")
    except ValueError as ve:
        typer.secho(f"ERROR: {ve}", fg=typer.colors.RED)
    except Exception as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED)
