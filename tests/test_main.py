import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from gmail_copy_tool.main import app, credentials_help, check_and_fix_tokens


class TestMainApp:
    """Test the main CLI application."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_credentials_help_command(self):
        """Test the credentials-help command outputs help text."""
        result = self.runner.invoke(app, ["credentials-help"])
        assert result.exit_code == 0
        assert "How to obtain credentials.json" in result.output
        assert "Google Cloud Console" in result.output
        assert "OAuth client ID" in result.output

    def test_credentials_help_function_direct(self, capsys):
        """Test the credentials_help function directly."""
        credentials_help()
        captured = capsys.readouterr()
        assert "How to obtain credentials.json" in captured.out
        assert "Google Cloud Console" in captured.out

    @patch('gmail_copy_tool.main.os.path.exists')
    @patch('gmail_copy_tool.main.delete_duplicates')
    def test_check_and_fix_tokens_missing_source(self, mock_delete_duplicates, mock_exists):
        """Test check_and_fix_tokens when source token is missing."""
        # Mock source token missing, target token exists
        mock_exists.side_effect = lambda path: "sangennaroarchivio4" in path
        
        check_and_fix_tokens()
        
        # Should call delete_duplicates for the missing source token
        mock_delete_duplicates.assert_called_once_with(
            account="sangennaroarchivio3@gmail.com",
            credentials="credentials_source.json"
        )

    @patch('gmail_copy_tool.main.os.path.exists')
    @patch('gmail_copy_tool.main.delete_duplicates')
    def test_check_and_fix_tokens_missing_target(self, mock_delete_duplicates, mock_exists):
        """Test check_and_fix_tokens when target token is missing."""
        # Mock target token missing, source token exists
        mock_exists.side_effect = lambda path: "sangennaroarchivio3" in path
        
        check_and_fix_tokens()
        
        # Should call delete_duplicates for the missing target token
        mock_delete_duplicates.assert_called_once_with(
            account="sangennaroarchivio4@gmail.com",
            credentials="credentials_target.json"
        )

    @patch('gmail_copy_tool.main.os.path.exists')
    @patch('gmail_copy_tool.main.delete_duplicates')
    def test_check_and_fix_tokens_both_missing(self, mock_delete_duplicates, mock_exists):
        """Test check_and_fix_tokens when both tokens are missing."""
        # Mock both tokens missing
        mock_exists.return_value = False
        
        check_and_fix_tokens()
        
        # Should call delete_duplicates twice
        assert mock_delete_duplicates.call_count == 2
        calls = mock_delete_duplicates.call_args_list
        assert any("sangennaroarchivio3@gmail.com" in str(call) for call in calls)
        assert any("sangennaroarchivio4@gmail.com" in str(call) for call in calls)

    @patch('gmail_copy_tool.main.os.path.exists')
    @patch('gmail_copy_tool.main.delete_duplicates')
    def test_check_and_fix_tokens_both_exist(self, mock_delete_duplicates, mock_exists):
        """Test check_and_fix_tokens when both tokens exist."""
        # Mock both tokens existing
        mock_exists.return_value = True
        
        check_and_fix_tokens()
        
        # Should not call delete_duplicates
        mock_delete_duplicates.assert_not_called()

    def test_app_has_all_commands(self):
        """Test that the app has all expected commands registered."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        
        # Check that all commands are listed
        commands = ["analyze", "compare", "copy", "delete-duplicates", "remove-copied", "setup", "list", "credentials-help"]
        for command in commands:
            assert command in result.output

    def test_invalid_command(self):
        """Test that invalid commands are handled properly."""
        result = self.runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output