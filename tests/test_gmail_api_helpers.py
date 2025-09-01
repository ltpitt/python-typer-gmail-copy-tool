import pytest
import time
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from gmail_copy_tool.utils.gmail_api_helpers import send_with_backoff, ensure_token


class TestGmailApiHelpers:
    """Test the Gmail API helper functions."""

    def test_send_with_backoff_success_first_try(self):
        """Test send_with_backoff succeeds on first attempt."""
        mock_send_func = MagicMock()
        mock_send_func.return_value = "success"
        
        result = send_with_backoff(mock_send_func, 5, 2, "arg1", "arg2", kwarg1="value1")
        
        assert result == "success"
        mock_send_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")

    @patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep')
    def test_send_with_backoff_rate_limit_with_retry_after_header(self, mock_sleep):
        """Test send_with_backoff handles rate limit with Retry-After header."""
        mock_send_func = MagicMock()
        
        # Create mock rate limit exception
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value="30")  # Retry after 30 seconds
        
        mock_send_func.side_effect = [rate_limit_error, "success"]
        
        result = send_with_backoff(mock_send_func, 2, 2)
        
        assert result == "success"
        assert mock_send_func.call_count == 2
        # Should sleep twice: once for rate limit (35s) and once for gentle delay (1s)  
        assert mock_sleep.call_count == 2
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert 35 in sleep_calls  # Rate limit + safety margin
        assert 1 in sleep_calls   # Gentle delay

    @patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep')
    def test_send_with_backoff_rate_limit_with_utc_retry_time(self, mock_sleep):
        """Test send_with_backoff handles rate limit with UTC retry time in error message."""
        mock_send_func = MagicMock()
        
        # Create mock rate limit exception with UTC retry time in content
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value=None)
        rate_limit_error.content = '{"error": {"message": "Retry after 2024-01-01T12:30:00.000Z"}}'
        
        mock_send_func.side_effect = [rate_limit_error, "success"]
        
        result = send_with_backoff(mock_send_func, 2, 2)
        
        assert result == "success"
        assert mock_send_func.call_count == 2
        # Should sleep (the exact time calculation is complex, just verify it was called)
        assert mock_sleep.called

    @patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep')
    def test_send_with_backoff_rate_limit_exponential_backoff(self, mock_sleep):
        """Test send_with_backoff uses exponential backoff when no retry time provided."""
        mock_send_func = MagicMock()
        
        # Create mock rate limit exception without retry info
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value=None)
        
        mock_send_func.side_effect = [rate_limit_error, rate_limit_error, "success"]
        
        result = send_with_backoff(mock_send_func, 3, 2)
        
        assert result == "success"
        assert mock_send_func.call_count == 3
        
        # Should use exponential backoff: 2, then 4 seconds, plus gentle delays (1s each)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert 2 in sleep_calls  # First exponential backoff
        assert 4 in sleep_calls  # Second exponential backoff (doubled)
        assert 1 in sleep_calls  # Final gentle delay

    def test_send_with_backoff_non_rate_limit_error(self):
        """Test send_with_backoff stops on non-rate-limit errors."""
        mock_send_func = MagicMock()
        
        # Create non-rate-limit exception
        other_error = Exception("Some other error")
        other_error.resp = MagicMock()
        other_error.resp.status = 500
        
        mock_send_func.side_effect = other_error
        
        result = send_with_backoff(mock_send_func, 3, 2)
        
        assert result is None
        assert mock_send_func.call_count == 1  # Should not retry

    def test_send_with_backoff_max_retries_exceeded(self):
        """Test send_with_backoff gives up after max retries."""
        mock_send_func = MagicMock()
        
        # Create rate limit error that persists
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value=None)
        
        mock_send_func.side_effect = rate_limit_error
        
        with patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep'):
            result = send_with_backoff(mock_send_func, 2, 2)
        
        assert result is None
        assert mock_send_func.call_count == 2

    @patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep')
    def test_send_with_backoff_adds_small_delay_between_sends(self, mock_sleep):
        """Test send_with_backoff adds small delay between successful sends."""
        mock_send_func = MagicMock()
        mock_send_func.return_value = "success"
        
        result = send_with_backoff(mock_send_func, 5, 2)
        
        assert result == "success"
        mock_sleep.assert_called_with(1)  # Should add 1 second delay

    def test_send_with_backoff_json_error_parsing(self):
        """Test send_with_backoff can parse JSON error content."""
        mock_send_func = MagicMock()
        
        # Create rate limit error with JSON content
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value=None)
        rate_limit_error.content = b'{"error": {"message": "Custom rate limit message"}}'
        
        mock_send_func.side_effect = [rate_limit_error, "success"]
        
        with patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep'):
            result = send_with_backoff(mock_send_func, 2, 2)
        
        assert result == "success"

    def test_send_with_backoff_invalid_json_content(self):
        """Test send_with_backoff handles invalid JSON content gracefully."""
        mock_send_func = MagicMock()
        
        # Create rate limit error with invalid JSON content
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value=None)
        rate_limit_error.content = b'invalid json content'
        
        mock_send_func.side_effect = [rate_limit_error, "success"]
        
        with patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep'):
            result = send_with_backoff(mock_send_func, 2, 2)
        
        assert result == "success"

    @patch('gmail_copy_tool.utils.gmail_api_helpers.os.path.exists')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.Credentials.from_authorized_user_file')
    def test_ensure_token_valid_token_exists(self, mock_creds_from_file, mock_exists):
        """Test ensure_token when valid token already exists."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_from_file.return_value = mock_creds
        
        # Should not create new token
        ensure_token("token.json", "credentials.json", "https://www.googleapis.com/auth/gmail.readonly")
        
        mock_creds_from_file.assert_called_once_with("token.json", ["https://www.googleapis.com/auth/gmail.readonly"])

    @patch('gmail_copy_tool.utils.gmail_api_helpers.os.path.exists')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.InstalledAppFlow.from_client_secrets_file')
    def test_ensure_token_no_token_file(self, mock_flow_from_file, mock_exists):
        """Test ensure_token when no token file exists."""
        mock_exists.return_value = False
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_from_file.return_value = mock_flow
        
        with patch('builtins.open', mock_open()) as mock_file:
            ensure_token("token.json", "credentials.json", "https://www.googleapis.com/auth/gmail.readonly")
        
        mock_flow_from_file.assert_called_once_with("credentials.json", ["https://www.googleapis.com/auth/gmail.readonly"])
        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_file.assert_called_with("token.json", 'w')

    @patch('gmail_copy_tool.utils.gmail_api_helpers.os.path.exists')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.Credentials.from_authorized_user_file')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.InstalledAppFlow.from_client_secrets_file')
    def test_ensure_token_invalid_token_exists(self, mock_flow_from_file, mock_creds_from_file, mock_exists):
        """Test ensure_token when invalid token exists."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds_from_file.return_value = mock_creds
        
        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_from_file.return_value = mock_flow
        
        with patch('builtins.open', mock_open()) as mock_file:
            ensure_token("token.json", "credentials.json", "https://www.googleapis.com/auth/gmail.readonly")
        
        # Should create new credentials
        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_file.assert_called_with("token.json", 'w')

    @patch('gmail_copy_tool.utils.gmail_api_helpers.os.path.exists')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.Credentials.from_authorized_user_file')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.InstalledAppFlow.from_client_secrets_file')
    def test_ensure_token_exception_loading_token(self, mock_flow_from_file, mock_creds_from_file, mock_exists):
        """Test ensure_token when exception occurs loading existing token."""
        mock_exists.return_value = True
        mock_creds_from_file.side_effect = Exception("Failed to load token")
        
        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_from_file.return_value = mock_flow
        
        with patch('builtins.open', mock_open()) as mock_file:
            ensure_token("token.json", "credentials.json", "https://www.googleapis.com/auth/gmail.readonly")
        
        # Should create new credentials
        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_file.assert_called_with("token.json", 'w')

    def test_send_with_backoff_logging(self):
        """Test that send_with_backoff logs appropriately."""
        mock_send_func = MagicMock()
        mock_send_func.return_value = "success"
        
        with patch('gmail_copy_tool.utils.gmail_api_helpers.logger') as mock_logger:
            result = send_with_backoff(mock_send_func, 5, 2)
        
        assert result == "success"
        # Should log debug message about attempt
        mock_logger.debug.assert_called()

    @patch('gmail_copy_tool.utils.gmail_api_helpers.print')
    @patch('gmail_copy_tool.utils.gmail_api_helpers.time.sleep')
    def test_send_with_backoff_console_output(self, mock_sleep, mock_print):
        """Test that send_with_backoff prints rate limit messages to console."""
        mock_send_func = MagicMock()
        
        # Create rate limit error
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.resp = MagicMock()
        rate_limit_error.resp.status = 429
        rate_limit_error.resp.get = MagicMock(return_value="30")
        
        mock_send_func.side_effect = [rate_limit_error, "success"]
        
        result = send_with_backoff(mock_send_func, max_retries=2)
        
        assert result == "success"
        # Should print rate limit messages
        assert mock_print.called
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Rate limit hit" in call for call in print_calls)