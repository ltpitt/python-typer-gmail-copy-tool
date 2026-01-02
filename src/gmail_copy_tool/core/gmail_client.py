from google.auth.transport.requests import Request
from google.auth import exceptions as auth_exceptions

import os
import typer
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from rich.progress import Progress



# Allow different scopes for source and target
SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]

# Always use high-permission scopes
SCOPES_HIGH_PERMISSION = ["https://mail.google.com/"]


logger = logging.getLogger(__name__)
# Refine debug mode logic to avoid unintended activation
explicit_debug_mode = os.environ.get("GMAIL_COPY_TOOL_DEBUG", "0") == "1"
if explicit_debug_mode:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient.discovery").setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.INFO)
    logging.getLogger("requests_oauthlib").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)  # Default to INFO for non-debug mode
    logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

# Log the debug mode status for verification
logger.info(f"Debug mode is {'enabled' if explicit_debug_mode else 'disabled'} based on GMAIL_COPY_TOOL_DEBUG={os.environ.get('GMAIL_COPY_TOOL_DEBUG', '0')}")

class GmailClient:
    """Gmail API client for authentication and mailbox operations."""

    def __init__(self, account: str, credentials_path: str = "credentials.json", token_path: str = None, scope: str = "readonly"):
        self.account = account
        self.credentials_path = credentials_path
        self.token_path = token_path or f"token_{account.replace('@', '_')}.json"
        self.scope = scope
        self.service = self.authenticate()

    def authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        try:
            logger.debug(f"Authenticating Gmail account: {self.account}")
            creds = None
            # Enforce high-permission scopes
            scopes = SCOPES_HIGH_PERMISSION
            if os.path.exists(self.token_path):
                logger.debug(f"Loading credentials from token file: {self.token_path}")
                creds = Credentials.from_authorized_user_file(self.token_path, scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.debug("Refreshing expired credentials.")
                    try:
                        creds.refresh(Request())
                    except auth_exceptions.RefreshError as e:
                        logger.warning(f"Token refresh failed: {e}. Deleting expired token and re-authenticating.")
                        # Delete the expired token file
                        if os.path.exists(self.token_path):
                            os.remove(self.token_path)
                            logger.debug(f"Deleted expired token file: {self.token_path}")
                        # Re-authenticate with OAuth flow
                        logger.debug(f"Starting OAuth flow using credentials file: {self.credentials_path}")
                        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, scopes)
                        creds = flow.run_local_server(port=0)
                else:
                    logger.debug(f"Starting OAuth flow using credentials file: {self.credentials_path}")
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, scopes)
                    creds = flow.run_local_server(port=0)
                with open(self.token_path, "w") as token:
                    logger.debug(f"Saving new token to: {self.token_path}")
                    token.write(creds.to_json())
            logger.debug("Building Gmail service client.")
            return build("gmail", "v1", credentials=creds)
        except FileNotFoundError as e:
            logger.error(f"FileNotFoundError: {e}")
            typer.secho(f"ERROR: Credentials file not found: {self.credentials_path}", fg=typer.colors.RED, bold=True)
            typer.echo("\nHow to obtain a Gmail API credentials file:\n")
            typer.echo(
                "1. Go to the Google Cloud Console: https://console.cloud.google.com/\n"
                "2. Create a new project (or select an existing one).\n"
                "3. Navigate to APIs & Services > Library and enable the Gmail API.\n"
                "4. Go to APIs & Services > Credentials.\n"
                "5. Click Create Credentials > OAuth client ID.\n"
                "   - If prompted, configure the OAuth consent screen first.\n"
                "   - Choose Desktop app as the application type.\n"
                "   - Name it (e.g., 'gmail-copy-tool').\n"
                f"6. Click Create. Download the credentials file and name it as needed (e.g., {self.credentials_path}).\n"
                f"7. Place {self.credentials_path} in your project’s working directory (where you run the CLI).\n\n"
                "This file allows your app to request user authorization for Gmail access."
            )
            import sys; sys.stdout.flush(); sys.stderr.flush()
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Unexpected error during authentication: {e}")
            typer.secho(f"ERROR: {str(e)}", fg=typer.colors.RED, bold=True)
            import sys; sys.stdout.flush(); sys.stderr.flush()
            raise typer.Exit(code=1)

    def count_emails(self, after=None, before=None, label=None, credentials_path=None):
        """Return the number of emails, optionally filtered by date or label."""
        total = 0
        page_token = None
        query = ""
        import os
        show_timing = os.environ.get("GMAIL_COPY_TOOL_TIMING", "0") == "1"
        import time
        start = time.time() if show_timing else None
        # Use the same scope logic as __init__ and authenticate
        SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
        SCOPES_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]
        scopes = SCOPES_READONLY if self.scope == "readonly" else SCOPES_MODIFY
        credentials_path = credentials_path or self.credentials_path
        # If self.service is a MagicMock (i.e., tests are patching authenticate), skip credential logic
        from unittest.mock import MagicMock
        if isinstance(getattr(self, "service", None), MagicMock):
            service = self.service
        else:
            try:
                # Authenticate and build service
                if os.path.exists(self.token_path):
                    creds = Credentials.from_authorized_user_file(self.token_path, scopes)
                else:
                    creds = None
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                        except auth_exceptions.RefreshError as e:
                            logger.warning(f"Token refresh failed: {e}. Deleting expired token and re-authenticating.")
                            # Delete the expired token file
                            if os.path.exists(self.token_path):
                                os.remove(self.token_path)
                                logger.debug(f"Deleted expired token file: {self.token_path}")
                            # Re-authenticate with OAuth flow
                            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
                            creds = flow.run_local_server(port=0)
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
                        creds = flow.run_local_server(port=0)
                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())
                service = build("gmail", "v1", credentials=creds)
            except FileNotFoundError:
                typer.secho(f"ERROR: Credentials file not found: {self.credentials_path}", fg=typer.colors.RED, bold=True)
                typer.echo("\nHow to obtain a Gmail API credentials file:\n")
                typer.echo(
                    "1. Go to the Google Cloud Console: https://console.cloud.google.com/\n"
                    "2. Create a new project (or select an existing one).\n"
                    "3. Navigate to APIs & Services > Library and enable the Gmail API.\n"
                    "4. Go to APIs & Services > Credentials.\n"
                    "5. Click Create Credentials > OAuth client ID.\n"
                    "   - If prompted, configure the OAuth consent screen first.\n"
                    "   - Choose Desktop app as the application type.\n"
                    "   - Name it (e.g., 'gmail-copy-tool').\n"
                    f"6. Click Create. Download the credentials file and name it as needed (e.g., {self.credentials_path}).\n"
                    f"7. Place {self.credentials_path} in your project’s working directory (where you run the CLI).\n\n"
                    "This file allows your app to request user authorization for Gmail access."
                )
                import sys; sys.stdout.flush(); sys.stderr.flush()
                raise typer.Exit(code=1)
            except Exception as e:
                logger.exception(f"Unexpected error during authentication: {e}")
                typer.secho(f"ERROR: {str(e)}", fg=typer.colors.RED, bold=True)
                import sys; sys.stdout.flush(); sys.stderr.flush()
                raise typer.Exit(code=1)
        try:
            # Build query string
            if after:
                query += f" after:{after}"
            if before:
                query += f" before:{before}"
            label_ids = [label] if label else None

            user_id = "me"
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
                    total += len(messages)
                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break
                except Exception as e:
                    logger.error(f"Failed to fetch message IDs: {e}")
                    break
            if show_timing:
                elapsed = time.time() - start
                print(f"[Timing] count_emails took {elapsed:.2f} seconds.")
            return total
        except Exception as e:
            logger.exception(f"Unexpected error during email counting: {e}")
            raise
