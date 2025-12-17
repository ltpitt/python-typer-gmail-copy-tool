import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open, call
from gmail_copy_tool.core.gmail_client import GmailClient, SCOPES_READONLY, SCOPES_MODIFY, SCOPES_HIGH_PERMISSION
import typer


class TestGmailClient:
    """Test the GmailClient class."""

    def test_init_default_values(self):
        """Test GmailClient initialization with default values."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_auth.return_value = MagicMock()
            
            client = GmailClient("test@gmail.com")
            
            assert client.account == "test@gmail.com"
            assert client.credentials_path == "credentials.json"
            assert client.token_path == "token_test_gmail.com.json"
            assert client.scope == "readonly"
            mock_auth.assert_called_once()

    def test_init_custom_values(self):
        """Test GmailClient initialization with custom values."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_auth.return_value = MagicMock()
            
            client = GmailClient(
                "test@gmail.com",
                credentials_path="custom_creds.json",
                token_path="custom_token.json",
                scope="modify"
            )
            
            assert client.account == "test@gmail.com"
            assert client.credentials_path == "custom_creds.json"
            assert client.token_path == "custom_token.json"
            assert client.scope == "modify"

    @patch('gmail_copy_tool.core.gmail_client.build')
    @patch('gmail_copy_tool.core.gmail_client.os.path.exists')
    @patch('gmail_copy_tool.core.gmail_client.Credentials.from_authorized_user_file')
    def test_authenticate_with_valid_token(self, mock_creds_from_file, mock_exists, mock_build):
        """Test authentication with valid existing token."""
        # Setup mocks
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_from_file.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        client = GmailClient("test@gmail.com")
        
        assert client.service == mock_service
        mock_creds_from_file.assert_called_once_with("token_test_gmail.com.json", SCOPES_HIGH_PERMISSION)
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)

    @patch('gmail_copy_tool.core.gmail_client.build')
    @patch('gmail_copy_tool.core.gmail_client.os.path.exists')
    @patch('gmail_copy_tool.core.gmail_client.Credentials.from_authorized_user_file')
    @patch('gmail_copy_tool.core.gmail_client.Request')
    def test_authenticate_with_expired_token(self, mock_request, mock_creds_from_file, mock_exists, mock_build):
        """Test authentication with expired token that can be refreshed."""
        # Setup mocks
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_from_file.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        with patch('builtins.open', mock_open()) as mock_file:
            client = GmailClient("test@gmail.com")
        
        assert client.service == mock_service
        mock_creds.refresh.assert_called_once()
        mock_file.assert_called_with("token_test_gmail.com.json", "w")

    @patch('gmail_copy_tool.core.gmail_client.build')
    @patch('gmail_copy_tool.core.gmail_client.os.path.exists')
    @patch('gmail_copy_tool.core.gmail_client.InstalledAppFlow.from_client_secrets_file')
    def test_authenticate_new_oauth_flow(self, mock_flow_from_file, mock_exists, mock_build):
        """Test authentication with new OAuth flow."""
        # Setup mocks
        mock_exists.return_value = False  # No existing token
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_from_file.return_value = mock_flow
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        with patch('builtins.open', mock_open()) as mock_file:
            client = GmailClient("test@gmail.com")
        
        assert client.service == mock_service
        mock_flow_from_file.assert_called_once_with("credentials.json", SCOPES_HIGH_PERMISSION)
        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_file.assert_called_with("token_test_gmail.com.json", "w")

    @patch('gmail_copy_tool.core.gmail_client.typer.Exit')
    @patch('gmail_copy_tool.core.gmail_client.typer.secho')
    @patch('gmail_copy_tool.core.gmail_client.typer.echo')
    @patch('gmail_copy_tool.core.gmail_client.os.path.exists')
    @patch('gmail_copy_tool.core.gmail_client.Credentials.from_authorized_user_file')
    def test_authenticate_file_not_found(self, mock_creds_from_file, mock_exists, mock_echo, mock_secho, mock_exit):
        """Test authentication when credentials file is not found."""
        # Setup mocks
        mock_exists.return_value = False
        mock_creds_from_file.side_effect = FileNotFoundError("File not found")
        mock_exit.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit):
            GmailClient("test@gmail.com")
        
        # Should call secho with error message
        mock_secho.assert_called()
        mock_exit.assert_called_once_with(code=1)

    @patch('gmail_copy_tool.core.gmail_client.typer.Exit')
    @patch('gmail_copy_tool.core.gmail_client.typer.secho')
    @patch('gmail_copy_tool.core.gmail_client.os.path.exists')
    @patch('gmail_copy_tool.core.gmail_client.Credentials.from_authorized_user_file')
    def test_authenticate_unexpected_error(self, mock_creds_from_file, mock_exists, mock_secho, mock_exit):
        """Test authentication with unexpected error."""
        # Setup mocks
        mock_exists.return_value = True
        mock_creds_from_file.side_effect = Exception("Unexpected error")
        mock_exit.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit):
            GmailClient("test@gmail.com")
        
        mock_secho.assert_called()
        mock_exit.assert_called_once_with(code=1)

    def test_count_emails_with_mock_service(self):
        """Test count_emails method with mocked service."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value = mock_service
            
            # Setup mock responses
            mock_response1 = {
                'messages': [{'id': '1'}, {'id': '2'}],
                'nextPageToken': 'token123'
            }
            mock_response2 = {
                'messages': [{'id': '3'}],
                # No nextPageToken to end pagination
            }
            
            mock_service.users().messages().list().execute.side_effect = [mock_response1, mock_response2]
            
            client = GmailClient("test@gmail.com")
            count = client.count_emails()
            
            assert count == 3
            assert mock_service.users().messages().list().execute.call_count == 2

    def test_count_emails_with_filters(self):
        """Test count_emails method with date and label filters."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value = mock_service
            
            mock_response = {
                'messages': [{'id': '1'}, {'id': '2'}],
            }
            mock_service.users().messages().list().execute.return_value = mock_response
            
            client = GmailClient("test@gmail.com")
            count = client.count_emails(after="2023-01-01", before="2023-12-31", label="INBOX")
            
            assert count == 2
            # Verify that the query and label filters were used
            call_args = mock_service.users().messages().list.call_args
            assert 'q' in call_args[1]
            assert 'after:2023-01-01' in call_args[1]['q']
            assert 'before:2023-12-31' in call_args[1]['q']
            assert call_args[1]['labelIds'] == ["INBOX"]

    def test_count_emails_with_empty_result(self):
        """Test count_emails method with empty result."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value = mock_service
            
            mock_response = {'messages': []}
            mock_service.users().messages().list().execute.return_value = mock_response
            
            client = GmailClient("test@gmail.com")
            count = client.count_emails()
            
            assert count == 0

    def test_count_emails_with_exception(self):
        """Test count_emails method handling exceptions during API calls."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value = mock_service
            
            # First call succeeds, second call fails
            mock_response = {
                'messages': [{'id': '1'}],
                'nextPageToken': 'token123'
            }
            mock_service.users().messages().list().execute.side_effect = [
                mock_response,
                Exception("API Error")
            ]
            
            client = GmailClient("test@gmail.com")
            count = client.count_emails()
            
            # Should return count from first successful call
            assert count == 1

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_TIMING': '1'})
    def test_count_emails_with_timing(self, capsys):
        """Test count_emails method with timing enabled."""
        with patch.object(GmailClient, 'authenticate') as mock_auth:
            mock_service = MagicMock()
            mock_auth.return_value = mock_service
            
            mock_response = {'messages': [{'id': '1'}]}
            mock_service.users().messages().list().execute.return_value = mock_response
            
            client = GmailClient("test@gmail.com")
            count = client.count_emails()
            
            captured = capsys.readouterr()
            assert "[Timing] count_emails took" in captured.out
            assert count == 1

    def test_scope_constants(self):
        """Test that scope constants are properly defined."""
        assert SCOPES_READONLY == ["https://www.googleapis.com/auth/gmail.readonly"]
        assert SCOPES_MODIFY == ["https://www.googleapis.com/auth/gmail.modify"]  
        assert SCOPES_HIGH_PERMISSION == ["https://mail.google.com/"]

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '1'})
    def test_debug_mode_enabled(self):
        """Test that debug mode is properly enabled."""
        with patch('gmail_copy_tool.core.gmail_client.logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            # Import after setting environment variable
            import importlib
            import gmail_copy_tool.core.gmail_client
            importlib.reload(gmail_copy_tool.core.gmail_client)
            
            # Verify that debug level was set
            mock_logger.setLevel.assert_called_with(10)  # DEBUG level

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'})
    def test_debug_mode_disabled(self):
        """Test that debug mode is properly disabled."""
        with patch('gmail_copy_tool.core.gmail_client.logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            # Import after setting environment variable
            import importlib
            import gmail_copy_tool.core.gmail_client
            importlib.reload(gmail_copy_tool.core.gmail_client)
            
            # Verify that warning level was set (based on actual module behavior)
            mock_logger.setLevel.assert_called_with(30)  # WARNING level