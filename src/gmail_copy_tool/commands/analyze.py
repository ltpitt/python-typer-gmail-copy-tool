import typer
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()

@app.command()

def analyze(
    account: str = typer.Option(..., help="Gmail account email address"),
    credentials: str = typer.Option("credentials_source.json", help="Path to credentials file for this account (default: credentials_source.json)"),
    after: str = typer.Option(None, help="Count emails after this date (YYYY-MM-DD)"),
    before: str = typer.Option(None, help="Count emails before this date (YYYY-MM-DD)"),
    label: str = typer.Option(None, help="Count emails with this Gmail label")
):
    """Count total number of emails in the specified Gmail account, with optional filters."""
    typer.echo(f"Analyzing account: {account}")
    try:
        client = GmailClient(account, credentials_path=credentials)
        total = client.count_emails(after=after, before=before, label=label)
        typer.echo(f"Total emails: {total}")
    except typer.Exit:
        pass
    except Exception as e:
        typer.secho(f"ERROR: {str(e)}", fg=typer.colors.RED, bold=True)
        import sys; sys.stdout.flush(); sys.stderr.flush()
