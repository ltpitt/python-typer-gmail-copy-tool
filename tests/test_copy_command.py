import pytest
import os
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from gmail_copy_tool.commands.copy import copy, app


class TestCopyCommand:
    """Test the copy command basic functionality."""

    def setup_method(self):
        self.runner = CliRunner()

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_debug_mode_setup(self, mock_gmail_client):
        """Test copy command debug mode configuration."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock to prevent deep execution
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.return_value = []
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.side_effect = [
                    {"email": "source@gmail.com", "credentials": "creds_src.json", "token": None},
                    {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": None}
                ]
                
                # Test debug mode enabled
                with patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '1'}):
                    result = self.runner.invoke(app, ["test-source", "test-target"])
                    
                    # Should not fail even if it doesn't complete due to mocking
                    assert "Copying emails: source@gmail.com -> target@gmail.com" in result.output

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_debug_mode_disabled(self, mock_gmail_client):
        """Test copy command with debug mode disabled."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock to prevent deep execution
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.return_value = []
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.side_effect = [
                    {"email": "source@gmail.com", "credentials": "creds_src.json", "token": None},
                    {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": None}
                ]
                
                # Test debug mode disabled
                with patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'}):
                    result = self.runner.invoke(app, ["test-source", "test-target"])
                    
                    # Should not fail even if it doesn't complete due to mocking
                    assert "Copying emails: source@gmail.com -> target@gmail.com" in result.output

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_gmail_client_creation(self, mock_gmail_client):
        """Test that copy command creates GmailClient instances correctly."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock to prevent deep execution
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.return_value = []
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.side_effect = [
                    {"email": "source@gmail.com", "credentials": "creds_src.json", "token": "token_src.json"},
                    {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": "token_tgt.json"}
                ]
                
                result = self.runner.invoke(app, ["test-source", "test-target"])
            
            # Verify GmailClient was called with correct parameters
            assert mock_gmail_client.call_count == 2
            
            # Check source client call
            source_call = mock_gmail_client.call_args_list[0]
            assert source_call[0] == ("source@gmail.com",)
            assert source_call[1]['credentials_path'] == "creds_src.json"
            assert source_call[1]['token_path'] == "token_src.json"
            assert source_call[1]['scope'] == "readonly"
            
            # Check target client call
            target_call = mock_gmail_client.call_args_list[1]
            assert target_call[0] == ("target@gmail.com",)
            assert target_call[1]['credentials_path'] == "creds_tgt.json"
            assert target_call[1]['token_path'] == "token_tgt.json"
            assert target_call[1]['scope'] == "mail.google.com"

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_exception_handling(self, mock_gmail_client):
        """Test copy command exception handling."""
        # Make GmailClient raise an exception
        mock_gmail_client.side_effect = Exception("Authentication failed")
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "source@gmail.com",
                "credentials": "creds_src.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-source", "test-target"])
        
        # Command should handle exception gracefully
        # The exact behavior depends on the exception handling in the copy function
        assert result.exit_code != 0 or "ERROR" in result.output or "failed" in result.output.lower()

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_with_filters(self, mock_gmail_client):
        """Test copy command with date and label filters."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock to prevent deep execution
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.return_value = ["msg1", "msg2"]
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.side_effect = [
                    {"email": "source@gmail.com", "credentials": "creds_src.json", "token": None},
                    {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": None}
                ]
                
                result = self.runner.invoke(app, [
                    "test-source", "test-target",
                    "--label", "INBOX",
                    "--after", "2023-01-01",
                    "--before", "2023-12-31"
                ])
            
            # Verify that _get_all_message_ids was called (might be called multiple times)
            assert mock_get_ids.called

    def test_copy_command_help(self):
        """Test copy command help output."""
        result = self.runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "Copy all emails from source to target Gmail account" in result.output
        # Look for the option names in the output (the actual text is there, just with ANSI codes)
        assert "source" in result.output
        assert "target" in result.output

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_checkpoint_option(self, mock_gmail_client):
        """Test copy command with checkpoint option."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock to prevent deep execution but allow checkpoint logic
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.return_value = []
            
            # Mock the Checkpoint import that happens inside the function
            with patch('gmail_copy_tool.utils.checkpoint.Checkpoint') as mock_checkpoint:
                mock_cp = MagicMock()
                mock_checkpoint.return_value = mock_cp
                
                # Mock config manager
                with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                    mock_config.return_value.resolve_account.side_effect = [
                        {"email": "source@gmail.com", "credentials": "creds_src.json", "token": None},
                        {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": None}
                    ]
                    
                    result = self.runner.invoke(app, [
                        "test-source", "test-target",
                        "--checkpoint", "/tmp/checkpoint.json"
                    ])
                    
                    # The command should execute without error
                    # We can't easily verify the checkpoint was created due to the import being inside the function
                    assert "Copying emails: source@gmail.com -> target@gmail.com" in result.output

    def test_copy_command_missing_required_args(self):
        """Test copy command with missing required arguments."""
        # Test missing both arguments
        result = self.runner.invoke(app, [])
        assert result.exit_code != 0
        
        # Test missing target
        result = self.runner.invoke(app, ["test-source"])
        assert result.exit_code != 0

    @patch('gmail_copy_tool.commands.copy.GmailClient')
    def test_copy_command_uses_internal_date_source(self, mock_gmail_client):
        """Test that copy command uses internalDateSource=dateHeader when inserting messages."""
        # Mock clients to avoid actual Gmail API calls
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_gmail_client.side_effect = [mock_source_client, mock_target_client]
        
        # Mock the service methods and return values
        mock_source_service = MagicMock()
        mock_target_service = MagicMock()
        mock_source_client.service = mock_source_service
        mock_target_client.service = mock_target_service
        
        # Mock message IDs retrieval
        with patch('gmail_copy_tool.commands.copy._get_all_message_ids') as mock_get_ids:
            mock_get_ids.side_effect = [
                ["test_message_id"],  # Source messages
                []  # Target messages (empty for deduplication check)
            ]
            
            # Mock the labels list call for label preservation
            mock_source_service.users().labels().list().execute.return_value = {'labels': []}
            mock_target_service.users().labels().list().execute.return_value = {'labels': []}
            
            # Mock the metadata call for the source message
            mock_metadata_response = {
                'payload': {'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'Message-ID', 'value': '<test@example.com>'}
                ]},
                'labelIds': ['INBOX']
            }
            mock_source_service.users().messages().get().execute.return_value = mock_metadata_response
            
            # Mock the raw message call - need to differentiate between metadata and raw format calls
            def mock_get_side_effect(*args, **kwargs):
                if kwargs.get('format') == 'raw':
                    mock_response = MagicMock()
                    mock_response.execute.return_value = {'raw': 'dGVzdCByYXcgZW1haWwgZGF0YQ=='}
                    return mock_response
                else:  # metadata format
                    mock_response = MagicMock()
                    mock_response.execute.return_value = mock_metadata_response
                    return mock_response
            
            mock_source_service.users().messages().get.side_effect = mock_get_side_effect
            
            # Mock the insert call
            mock_insert_response = {'id': 'new_message_id'}
            mock_insert_call = MagicMock()
            mock_insert_call.execute.return_value = mock_insert_response
            mock_target_service.users().messages().insert.return_value = mock_insert_call
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.copy.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.side_effect = [
                    {"email": "source@gmail.com", "credentials": "creds_src.json", "token": None},
                    {"email": "target@gmail.com", "credentials": "creds_tgt.json", "token": None}
                ]
                
                # Run the copy command
                result = self.runner.invoke(app, ["test-source", "test-target"])
            
            # Verify the insert call was made with internalDateSource=dateHeader
            mock_target_service.users().messages().insert.assert_called_with(
                userId="me",
                body={"raw": 'dGVzdCByYXcgZW1haWwgZGF0YQ=='},
                internalDateSource="dateHeader"
            )