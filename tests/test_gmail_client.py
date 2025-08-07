def test_count_emails_pagination(mock_auth):
    # Mock Gmail service
    mock_service = MagicMock()
    mock_auth.return_value = mock_service
    # Simulate two pages of results
    mock_service.users().messages().list().execute.side_effect = [
        {"messages": [{}]*500, "nextPageToken": "token1"},
        {"messages": [{}]*100, "nextPageToken": None}
    ]
    client = GmailClient("test@gmail.com")
    total = client.count_emails()
    assert total == 600
def test_count_emails_empty(mock_auth):
    mock_service = MagicMock()
    mock_auth.return_value = mock_service
    mock_service.users().messages().list().execute.return_value = {"messages": [], "nextPageToken": None}
    client = GmailClient("test@gmail.com")
    total = client.count_emails()
    assert total == 0

import pytest
from unittest.mock import patch, MagicMock

from gmail_copy_tool.core.gmail_client import GmailClient

@patch('gmail_copy_tool.core.gmail_client.GmailClient.authenticate')
def test_count_emails_pagination(mock_auth):
    # Mock Gmail service
    mock_service = MagicMock()
    mock_auth.return_value = mock_service
    # Simulate two pages of results
    mock_service.users().messages().list().execute.side_effect = [
        {"messages": [{}]*500, "nextPageToken": "token1"},
        {"messages": [{}]*100, "nextPageToken": None}
    ]
    client = GmailClient("test@gmail.com")
    total = client.count_emails()
    assert total == 600

@patch('gmail_copy_tool.core.gmail_client.GmailClient.authenticate')
def test_count_emails_empty(mock_auth):
    mock_service = MagicMock()
    mock_auth.return_value = mock_service
    mock_service.users().messages().list().execute.return_value = {"messages": [], "nextPageToken": None}
    client = GmailClient("test@gmail.com")
    total = client.count_emails()
    assert total == 0
