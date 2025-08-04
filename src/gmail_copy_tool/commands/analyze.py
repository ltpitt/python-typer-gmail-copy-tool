import typer
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()

@app.command()
def analyze(account: str = typer.Option(..., help="Gmail account email address")):
    """Count total number of emails in the specified Gmail account."""
    typer.echo(f"Analyzing account: {account}")
    client = GmailClient(account)
    total = client.count_emails()
    typer.echo(f"Total emails: {total}")
