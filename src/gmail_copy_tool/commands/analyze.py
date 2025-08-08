
import typer
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()

@app.command()
def analyze(
    account: str = typer.Option(..., help="Gmail account email address"),
    credentials: str = typer.Option("credentials_source.json", help="Path to credentials file for this account (default: credentials_source.json)"),
    token: str = typer.Option(None, help="Path to OAuth token file for this account (optional)"),
    after: str = typer.Option(None, help="Count emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Count emails before this date (YYYY-MM-DD)"),
    label: str = typer.Option(None, help="Count emails with this Gmail label")
):
    """Count emails in a Gmail account. Supports filters by date and label."""
    import os, logging
    debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
    if not debug_mode:
        logging.getLogger("gmail_copy_tool.core.gmail_client").setLevel(logging.WARNING)
    try:
        client = GmailClient(account, credentials_path=credentials, token_path=token)
        typer.echo(f"Analyzing account: {account}")
        count = client.count_emails(after=after, label=label)
        typer.echo(f"Total emails: {count}")
    except ValueError as ve:
        typer.secho(f"ERROR: {ve}", fg=typer.colors.RED)
    except Exception as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED)
