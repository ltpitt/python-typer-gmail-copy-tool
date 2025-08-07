import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
import logging

from gmail_copy_tool.commands import analyze, compare, copy, delete_duplicates

# Configure logging to capture debug output during tests
logging.basicConfig(level=logging.DEBUG)

runner = CliRunner()

# --- Analyze Command Tests ---
def test_analyze_success():
    with patch("gmail_copy_tool.commands.analyze.GmailClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.count_emails.return_value = 42
        result = runner.invoke(analyze.app, ["--account", "test@gmail.com"])
        assert result.exit_code == 0
        assert "Analyzing account: test@gmail.com" in result.output
        assert "Total emails: 42" in result.output

    # Test credentials option
    with patch("gmail_copy_tool.commands.analyze.GmailClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.count_emails.return_value = 99
        result = runner.invoke(analyze.app, ["--account", "test@gmail.com", "--credentials", "custom.json"])
        MockClient.assert_called_with("test@gmail.com", credentials_path="custom.json")
        assert "Total emails: 99" in result.output

    # Error handling
    with patch("gmail_copy_tool.commands.analyze.GmailClient", side_effect=Exception("fail")):
        result = runner.invoke(analyze.app, ["--account", "test@gmail.com"])
        assert "ERROR: fail" in result.output

# Edge case: missing required account argument
def test_analyze_missing_account():
    result = runner.invoke(analyze.app, [])
    assert result.exit_code != 0
    assert "Missing option '--account'" in result.output or "Error" in result.output

# Edge case: invalid date format
def test_analyze_invalid_date():
    with patch("gmail_copy_tool.commands.analyze.GmailClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.count_emails.side_effect = ValueError("Invalid date format")
        result = runner.invoke(analyze.app, ["--account", "test@gmail.com", "--after", "not-a-date"])
        assert "ERROR: Invalid date format" in result.output

# Help text coverage
def test_analyze_help():
    result = runner.invoke(analyze.app, ["--help"])
    assert result.exit_code == 0
    assert "Gmail account email address" in result.output
    assert "credentials_source.json" in result.output
    assert "Count emails after this date" in result.output
    assert "Count emails with this Gmail label" in result.output

# --- Compare Command Tests ---
def test_compare_success():
    with patch("gmail_copy_tool.commands.compare.GmailClient") as MockClient:
        source_client = MagicMock()
        target_client = MagicMock()
        MockClient.side_effect = [source_client, target_client]
        # Patch _get_all_message_ids to return controlled sets
        with patch("gmail_copy_tool.commands.compare._get_all_message_ids") as mock_get_ids:
            mock_get_ids.side_effect = [
                ["id1", "id2", "id3"],  # source
                ["id2", "id3", "id4"]   # target
            ]
            result = runner.invoke(compare.app, [
                "--source", "src@gmail.com", "--target", "tgt@gmail.com"
            ])
            assert result.exit_code == 0
            # Assert on rich output panel title and IDs
            assert "📊 Comparison Summary" in result.output
            assert "id1" in result.output
            assert "id4" in result.output

    # Credentials file options
    with patch("gmail_copy_tool.commands.compare.GmailClient") as MockClient:
        source_client = MagicMock()
        target_client = MagicMock()
        MockClient.side_effect = [source_client, target_client]
        with patch("gmail_copy_tool.commands.compare._get_all_message_ids", return_value=[]):
            result = runner.invoke(compare.app, [
                "--source", "src@gmail.com", "--target", "tgt@gmail.com",
                "--credentials-source", "src.json", "--credentials-target", "tgt.json"
            ])
            MockClient.assert_any_call("src@gmail.com", credentials_path="src.json")
            MockClient.assert_any_call("tgt@gmail.com", credentials_path="tgt.json")

    # Error handling
    with patch("gmail_copy_tool.commands.compare.GmailClient", side_effect=Exception("fail")):
        result = runner.invoke(compare.app, ["--source", "src@gmail.com", "--target", "tgt@gmail.com"])
        assert "ERROR: fail" in result.output

# --- Copy Command Tests ---
def test_copy_success():
    with patch("gmail_copy_tool.commands.copy.GmailClient") as MockClient:
        source_client = MagicMock()
        target_client = MagicMock()
        MockClient.side_effect = [source_client, target_client]
        # Patch _get_all_message_ids to return a few IDs
        with patch("gmail_copy_tool.commands.copy._get_all_message_ids", return_value=["id1", "id2"]):
            result = runner.invoke(copy.app, [
                "--source", "src@gmail.com", "--target", "tgt@gmail.com"
            ])
            assert result.exit_code == 0
            assert "Copy operation completed." in result.output

    # Credentials file options
    with patch("gmail_copy_tool.commands.copy.GmailClient") as MockClient:
        source_client = MagicMock()
        target_client = MagicMock()
        MockClient.side_effect = [source_client, target_client]
        with patch("gmail_copy_tool.commands.copy._get_all_message_ids", return_value=[]):
            result = runner.invoke(copy.app, [
                "--source", "src@gmail.com", "--target", "tgt@gmail.com",
                "--credentials-source", "src.json", "--credentials-target", "tgt.json"
            ])
            MockClient.assert_any_call("src@gmail.com", credentials_path="src.json", scope="readonly")
            MockClient.assert_any_call("tgt@gmail.com", credentials_path="tgt.json", scope="mail.google.com")

    # Error handling
    with patch("gmail_copy_tool.commands.copy.GmailClient", side_effect=Exception("fail")):
        result = runner.invoke(copy.app, ["--source", "src@gmail.com", "--target", "tgt@gmail.com"])
        assert "ERROR: fail" in result.output

# --- Delete-Duplicates Command Tests ---
def test_delete_duplicates_success():
    with patch("gmail_copy_tool.commands.delete_duplicates.GmailClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.delete_duplicates.return_value = None  # Simulate successful operation
        result = runner.invoke(delete_duplicates.app, [
            "--account", "test@gmail.com",
            "--credentials", "mock_credentials.json"
        ])
        print(f"[DEBUG] Mock delete_duplicates return value: {mock_client.delete_duplicates.return_value}")
        print(f"[DEBUG] CLI command output: {result.output}")
        assert result.exit_code == 0
        assert "Duplicate email cleanup completed" in result.output

# Edge case: missing required account argument
def test_delete_duplicates_missing_account():
    result = runner.invoke(delete_duplicates.app, [])
    assert result.exit_code != 0
    assert "Missing option '--account'" in result.output or "Error" in result.output
