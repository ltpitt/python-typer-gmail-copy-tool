import typer
import os 

from gmail_copy_tool.commands.analyze import analyze
from gmail_copy_tool.commands.compare import compare
from gmail_copy_tool.commands.copy import copy

from gmail_copy_tool.commands.delete_duplicates import delete_duplicates
from gmail_copy_tool.commands.remove_copied import remove_copied


import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# Suppress googleapiclient.discovery_cache INFO logs
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)

app = typer.Typer()
app.command()(analyze)
app.command()(compare)
app.command()(copy)
app.command()(delete_duplicates)
app.command()(remove_copied)

@app.command()
def hello():
    """Print a hello message."""
    print("Hello from gmail-copy-tool!")
    
@app.command()
def credentials_help():
    """Show how to obtain Gmail API credentials.json."""
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


def check_and_fix_tokens():
    source_token = "token_sangennaroarchivio3_gmail.com.json"
    target_token = "token_sangennaroarchivio4_gmail.com.json"

    if not os.path.exists(source_token):
        print(f"[INFO] Source token {source_token} is missing. Running delete-duplicates to fix.")
        delete_duplicates(
            account="sangennaroarchivio3@gmail.com",
            credentials="credentials_source.json"
        )

    if not os.path.exists(target_token):
        print(f"[INFO] Target token {target_token} is missing. Running delete-duplicates to fix.")
        delete_duplicates(
            account="sangennaroarchivio4@gmail.com",
            credentials="credentials_target.json"
        )


if __name__ == "__main__":
    check_and_fix_tokens
    app()
