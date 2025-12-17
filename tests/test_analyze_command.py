import pytest
import os
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from gmail_copy_tool.commands.analyze import analyze, app


class TestAnalyzeCommand:
    """Test the analyze command."""

    def setup_method(self):
        self.runner = CliRunner()

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'})
    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_success(self, mock_gmail_client):
        """Test successful analyze command execution."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.count_emails.return_value = 150
        mock_gmail_client.return_value = mock_client
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        assert "Analyzing account: test@gmail.com" in result.output
        assert "Total emails: 150" in result.output
        
        # Verify GmailClient was called correctly
        mock_gmail_client.assert_called_once_with(
            "test@gmail.com",
            credentials_path="test_creds.json",
            token_path=None
        )
        mock_client.count_emails.assert_called_once_with(after=None, before=None, label=None)

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'})
    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_with_filters(self, mock_gmail_client):
        """Test analyze command with date and label filters."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.count_emails.return_value = 25
        mock_gmail_client.return_value = mock_client
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": "test_token.json"
            }
            
            result = self.runner.invoke(app, [
                "test-account",
                "--after", "2023-01-01",
                "--before", "2023-12-31",
                "--label", "INBOX"
            ])
        
        assert result.exit_code == 0
        assert "Analyzing account: test@gmail.com" in result.output
        assert "Total emails: 25" in result.output
        
        # Verify GmailClient was called correctly
        mock_gmail_client.assert_called_once_with(
            "test@gmail.com",
            credentials_path="test_creds.json",
            token_path="test_token.json"
        )
        mock_client.count_emails.assert_called_once_with(after="2023-01-01", before="2023-12-31", label="INBOX")

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '1'})
    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_debug_mode_enabled(self, mock_gmail_client):
        """Test analyze command with debug mode enabled."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.count_emails.return_value = 100
        mock_gmail_client.return_value = mock_client
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        # Verify client was called
        mock_gmail_client.assert_called_once()

    @patch.dict('os.environ', {'GMAIL_COPY_TOOL_DEBUG': '0'})
    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_debug_mode_disabled(self, mock_gmail_client):
        """Test analyze command with debug mode disabled."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.count_emails.return_value = 100
        mock_gmail_client.return_value = mock_client
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            # We can't easily test the logging import that happens inside the function,
            # but we can verify the command executes successfully when debug mode is disabled
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        mock_gmail_client.assert_called_once()

    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_value_error(self, mock_gmail_client):
        """Test analyze command handling ValueError."""
        # Setup mock to raise ValueError
        mock_gmail_client.side_effect = ValueError("Invalid credentials format")
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        assert "ERROR: Invalid credentials format" in result.output

    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_general_exception(self, mock_gmail_client):
        """Test analyze command handling general exceptions."""
        # Setup mock to raise general exception
        mock_gmail_client.side_effect = Exception("Network error")
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        assert "ERROR: Network error" in result.output

    @patch('gmail_copy_tool.commands.analyze.GmailClient')
    def test_analyze_command_count_emails_exception(self, mock_gmail_client):
        """Test analyze command when count_emails raises exception."""
        # Setup mock client that raises exception on count_emails
        mock_client = MagicMock()
        mock_client.count_emails.side_effect = Exception("API error")
        mock_gmail_client.return_value = mock_client
        
        # Mock config manager
        with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
            mock_config.return_value.resolve_account.return_value = {
                "email": "test@gmail.com",
                "credentials": "test_creds.json",
                "token": None
            }
            
            result = self.runner.invoke(app, ["test-account"])
        
        assert result.exit_code == 0
        assert "ERROR: API error" in result.output

    def test_analyze_command_default_credentials_path(self):
        """Test analyze command with default credentials path."""
        with patch('gmail_copy_tool.commands.analyze.GmailClient') as mock_gmail_client:
            mock_client = MagicMock()
            mock_client.count_emails.return_value = 50
            mock_gmail_client.return_value = mock_client
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.return_value = {
                    "email": "test@gmail.com",
                    "credentials": "test_creds.json",
                    "token": None
                }
                
                result = self.runner.invoke(app, ["test-account"])
            
            assert result.exit_code == 0
            
            # Should use provided credentials file
            mock_gmail_client.assert_called_once_with(
                "test@gmail.com",
                credentials_path="test_creds.json",
                token_path=None
            )

    def test_analyze_function_direct_call(self):
        """Test the analyze function called directly via CLI."""
        with patch('gmail_copy_tool.commands.analyze.GmailClient') as mock_gmail_client:
            mock_client = MagicMock()
            mock_client.count_emails.return_value = 75
            mock_gmail_client.return_value = mock_client
            
            # Mock config manager
            with patch('gmail_copy_tool.commands.analyze.ConfigManager') as mock_config:
                mock_config.return_value.resolve_account.return_value = {
                    "email": "direct@gmail.com",
                    "credentials": "direct_creds.json",
                    "token": "direct_token.json"
                }
                
                # Call via CLI with new syntax
                result = self.runner.invoke(app, [
                    "test-account",
                    "--after", "2023-06-01",
                    "--label", "Sent"
                ])
                
                # Verify calls
                mock_gmail_client.assert_called_once_with(
                    "direct@gmail.com",
                    credentials_path="direct_creds.json",
                    token_path="direct_token.json"
                )
                mock_client.count_emails.assert_called_once_with(after="2023-06-01", before=None, label="Sent")
                
                # Verify output
                assert result.exit_code == 0
                assert "Analyzing account: direct@gmail.com" in result.output
                assert "Total emails: 75" in result.output