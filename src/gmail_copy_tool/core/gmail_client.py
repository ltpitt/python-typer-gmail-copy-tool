
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from gmail_copy_tool.utils.timing import timing

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

class GmailClient:
    def __init__(self, account: str, credentials_path: str = "credentials.json", token_path: str = None):
        self.account = account
        self.credentials_path = credentials_path
        self.token_path = token_path or f"token_{account.replace('@', '_')}.json"
        self.service = self.authenticate()

    def authenticate(self):
        creds = None
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

    @timing
    def count_emails(self):
        # Count all emails in the account, excluding Spam, Trash, and Drafts
        total = 0
        page_token = None
        exclude_labels = ["SPAM", "TRASH", "DRAFT"]
        while True:
            results = self.service.users().messages().list(
                userId="me",
                pageToken=page_token,
                includeSpamTrash=False
            ).execute()
            messages = results.get("messages", [])
            total += len(messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        return total
