
import os
import typer
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from gmail_copy_tool.utils.timing import timing
from rich.progress import Progress


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

logger = logging.getLogger(__name__)

class GmailClient:
    def __init__(self, account: str, credentials_path: str = "credentials.json", token_path: str = None):
        self.account = account
        self.credentials_path = credentials_path
        self.token_path = token_path or f"token_{account.replace('@', '_')}.json"
        self.service = self.authenticate()

    def authenticate(self):
        try:
            logger.info(f"Authenticating Gmail account: {self.account}")
            creds = None
            if os.path.exists(self.token_path):
                logger.info(f"Loading credentials from token file: {self.token_path}")
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired credentials.")
                    creds.refresh(Request())
                else:
                    logger.info(f"Starting OAuth flow using credentials file: {self.credentials_path}")
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(self.token_path, "w") as token:
                    logger.info(f"Saving new token to: {self.token_path}")
                    token.write(creds.to_json())
            logger.info("Building Gmail service client.")
            return build("gmail", "v1", credentials=creds)
        except FileNotFoundError as e:
            logger.error(f"FileNotFoundError: {e}")
            typer.secho("ERROR: credentials.json not found!", fg=typer.colors.RED, bold=True)
            typer.echo("\nHow to obtain credentials.json for Gmail API access:\n")
            typer.echo(
                "1. Go to the Google Cloud Console: https://console.cloud.google.com/\n"
                "2. Create a new project (or select an existing one).\n"
                "3. Navigate to APIs & Services > Library and enable the Gmail API.\n"
                "4. Go to APIs & Services > Credentials.\n"
                "5. Click Create Credentials > OAuth client ID.\n"
                "   - If prompted, configure the OAuth consent screen first.\n"
                "   - Choose Desktop app as the application type.\n"
                "   - Name it (e.g., 'gmail-copy-tool').\n"
                "6. Click Create. Download the credentials.json file.\n"
                "7. Place credentials.json in your project’s working directory (where you run the CLI).\n\n"
                "This file allows your app to request user authorization for Gmail access."
            )
            import sys; sys.stdout.flush(); sys.stderr.flush()
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Unexpected error during authentication: {e}")
            typer.secho(f"ERROR: {str(e)}", fg=typer.colors.RED, bold=True)
            import sys; sys.stdout.flush(); sys.stderr.flush()
            raise typer.Exit(code=1)

    @timing
    def count_emails(self, after=None, before=None, label=None):
        """
        Count emails with optional filters:
        - after: YYYY-MM-DD
        - before: YYYY-MM-DD
        - label: Gmail label name
        """
        total = 0
        page_token = None
        query = ""
        try:
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
            return build("gmail", "v1", credentials=creds)
        except FileNotFoundError:
            typer.secho("ERROR: credentials.json not found!", fg=typer.colors.RED, bold=True)
            typer.echo("\nHow to obtain credentials.json for Gmail API access:\n")
            typer.echo(
                "1. Go to the Google Cloud Console: https://console.cloud.google.com/\n"
                "2. Create a new project (or select an existing one).\n"
                "3. Navigate to APIs & Services > Library and enable the Gmail API.\n"
                "4. Go to APIs & Services > Credentials.\n"
                "5. Click Create Credentials > OAuth client ID.\n"
                "   - If prompted, configure the OAuth consent screen first.\n"
                "   - Choose Desktop app as the application type.\n"
                "   - Name it (e.g., 'gmail-copy-tool').\n"
                "6. Click Create. Download the credentials.json file.\n"
                "7. Place credentials.json in your project’s working directory (where you run the CLI).\n\n"
                "This file allows your app to request user authorization for Gmail access."
            )
            import sys; sys.stdout.flush(); sys.stderr.flush()
            raise typer.Exit(code=1)
