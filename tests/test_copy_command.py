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
            
            # Test debug mode enabled
            with patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '1'}):
                result = self.runner.invoke(app, [
                    "--source", "source@gmail.com",
                    "--target", "target@gmail.com"
                ])
                
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
            
            # Test debug mode disabled
            with patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'}):
                result = self.runner.invoke(app, [
                    "--source", "source@gmail.com",
                    "--target", "target@gmail.com"
                ])
                
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
            
            result = self.runner.invoke(app, [
                "--source", "source@gmail.com",
                "--target", "target@gmail.com",
                "--credentials-source", "creds_src.json",
                "--credentials-target", "creds_tgt.json",
                "--token-source", "token_src.json",
                "--token-target", "token_tgt.json"
            ])
            
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
        
        result = self.runner.invoke(app, [
            "--source", "source@gmail.com",
            "--target", "target@gmail.com"
        ])
        
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
            
            result = self.runner.invoke(app, [
                "--source", "source@gmail.com",
                "--target", "target@gmail.com",
                "--label", "INBOX",
                "--after", "2023-01-01",
                "--before", "2023-12-31"
            ])
            
            # Verify that _get_all_message_ids was called (might be called multiple times)
            assert mock_get_ids.called
            # Check if any call had the right filters
            calls_with_filters = [call for call in mock_get_ids.call_args_list 
                                if len(call[1]) > 0 and call[1].get('label') == 'INBOX']
            assert len(calls_with_filters) > 0

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
                
                result = self.runner.invoke(app, [
                    "--source", "source@gmail.com",
                    "--target", "target@gmail.com",
                    "--checkpoint", "/tmp/checkpoint.json"
                ])
                
                # The command should execute without error
                # We can't easily verify the checkpoint was created due to the import being inside the function
                assert "Copying emails: source@gmail.com -> target@gmail.com" in result.output

    def test_copy_command_missing_required_args(self):
        """Test copy command with missing required arguments."""
        # Test missing source
        result = self.runner.invoke(app, ["--target", "target@gmail.com"])
        assert result.exit_code != 0
        
        # Test missing target
        result = self.runner.invoke(app, ["--source", "source@gmail.com"])
        assert result.exit_code != 0