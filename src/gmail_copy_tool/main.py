import typer
from gmail_copy_tool.commands import analyze

app = typer.Typer()
app.add_typer(analyze.app, name="analyze")

@app.command()
def hello():
    """Say hello!"""
    print("Hello from gmail-copy-tool!")
    
@app.command()
def credentials_help():
    """Show instructions for obtaining credentials.json for Gmail API access."""
    typer.echo("""
How to obtain credentials.json for Gmail API access:

1. Go to the Google Cloud Console: https://console.cloud.google.com/
2. Create a new project (or select an existing one).
3. Navigate to APIs & Services > Library and enable the Gmail API.
4. Go to APIs & Services > Credentials.
5. Click Create Credentials > OAuth client ID.
   - If prompted, configure the OAuth consent screen first.
   - Choose Desktop app as the application type.
   - Name it (e.g., 'gmail-copy-tool').
6. Click Create. Download the credentials.json file.
7. Place credentials.json in your project’s working directory (where you run the CLI).

This file allows your app to request user authorization for Gmail access.
""")

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app()
