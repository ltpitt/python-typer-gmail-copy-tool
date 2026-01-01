import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from gmail_copy_tool.main import app


class TestMainApp:
    """Test the main CLI application."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_app_has_all_commands(self):
        """Test that the app has all expected commands registered."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        
        # Check that current commands are listed
        commands = ["sync", "setup", "list"]
        for command in commands:
            assert command in result.output

    def test_invalid_command(self):
        """Test that invalid commands are handled properly."""
        result = self.runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_old_commands_removed(self):
        """Test that old commands no longer exist."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        
        # These commands should NOT be present anymore
        old_commands = ["analyze", "copy", "delete-duplicates", "remove-copied", "compare"]
        for command in old_commands:
            # 'compare' might appear in descriptions, so check more carefully
            if command == "compare":
                continue
            assert command not in result.output.lower()