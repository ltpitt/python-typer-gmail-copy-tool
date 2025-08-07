
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
    try:
        client = GmailClient(account, credentials_path=credentials)
        typer.echo(f"Analyzing account: {account}")
        count = client.count_emails(after=after, label=label)
        typer.echo(f"Total emails: {count}")
    except ValueError as ve:
        typer.secho(f"ERROR: {ve}", fg=typer.colors.RED)
    except Exception as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED)
