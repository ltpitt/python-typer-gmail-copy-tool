import pytest
import base64
import email
import hashlib
from unittest.mock import MagicMock, patch
from gmail_copy_tool.utils.canonicalization import compute_canonical_hash


class TestCanonicalization:
    """Test the canonicalization utility functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_service = MagicMock()
        self.mock_client.service = self.mock_service

    def test_compute_canonical_hash_simple_email(self):
        """Test canonical hash computation for a simple email."""
        # Create a simple email message
        email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

This is a test message body."""
        
        # Encode as base64 URL-safe
        raw_bytes = email_content.encode('utf-8')
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8')
        
        # Mock Gmail API response
        mock_response = {
            'raw': raw_b64
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "test_msg_id")
        
        assert hash_result is not None
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex digest length
        assert canonical_string is not None
        
        # Verify the canonical string contains expected headers
        assert "from: sender@example.com" in canonical_string
        assert "to: recipient@example.com" in canonical_string
        assert "subject: Test Subject" in canonical_string
        assert "date: Mon, 1 Jan 2024 12:00:00 +0000" in canonical_string
        assert "message-id: <test@example.com>" in canonical_string

    def test_compute_canonical_hash_multipart_email(self):
        """Test canonical hash computation for a multipart email."""
        # Create a multipart email
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        msg = MIMEMultipart()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Multipart Test'
        msg['Date'] = 'Mon, 1 Jan 2024 12:00:00 +0000'
        msg['Message-ID'] = '<multipart@example.com>'
        
        # Add text parts
        text_part = MIMEText("Plain text content", 'plain')
        html_part = MIMEText("<p>HTML content</p>", 'html')
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Convert to raw bytes and base64 encode
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8')
        
        # Mock Gmail API response
        mock_response = {
            'raw': raw_b64
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "multipart_msg_id")
        
        assert hash_result is not None
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        assert canonical_string is not None
        
        # Should contain headers
        assert "from: sender@example.com" in canonical_string
        assert "subject: Multipart Test" in canonical_string
        
        # Should contain content type and hash information for parts
        assert "text/plain||" in canonical_string
        assert "text/html||" in canonical_string

    def test_compute_canonical_hash_no_raw_content(self):
        """Test canonical hash computation when message has no raw content."""
        # Mock Gmail API response without raw content
        mock_response = {}
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "no_raw_msg_id")
        
        assert hash_result is None
        assert canonical_string is None

    def test_compute_canonical_hash_api_exception(self):
        """Test canonical hash computation when Gmail API raises exception."""
        # Mock Gmail API to raise exception
        self.mock_service.users().messages().get().execute.side_effect = Exception("API Error")
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "error_msg_id")
        
        assert hash_result is None
        assert canonical_string is None

    def test_compute_canonical_hash_invalid_base64(self):
        """Test canonical hash computation with invalid base64 content."""
        # Mock Gmail API response with invalid base64
        mock_response = {
            'raw': 'invalid_base64_content!!!'
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "invalid_b64_msg_id")
        
        assert hash_result is None
        assert canonical_string is None

    def test_compute_canonical_hash_header_normalization(self):
        """Test that headers are properly normalized in canonical string."""
        email_content = """FROM: Sender@Example.COM
TO: Recipient@Example.COM
SUBJECT:   Test Subject with Spaces   
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>
Custom-Header: Should be ignored

Test body content."""
        
        raw_bytes = email_content.encode('utf-8')
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8')
        
        mock_response = {
            'raw': raw_b64
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        hash_result, canonical_string = compute_canonical_hash(self.mock_client, "normalize_msg_id")
        
        assert hash_result is not None
        assert canonical_string is not None
        
        # Headers should be normalized to lowercase and stripped
        assert "from: Sender@Example.COM" in canonical_string
        assert "to: Recipient@Example.COM" in canonical_string
        assert "subject: Test Subject with Spaces" in canonical_string
        
        # Custom header should not be included (not in key_headers list)
        assert "custom-header" not in canonical_string.lower()

    def test_compute_canonical_hash_consistency(self):
        """Test that the same email produces the same canonical hash."""
        email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

Same message content."""
        
        raw_bytes = email_content.encode('utf-8')
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8')
        
        mock_response = {
            'raw': raw_b64
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        # Compute hash twice
        hash1, _ = compute_canonical_hash(self.mock_client, "consistency_msg_id_1")
        hash2, _ = compute_canonical_hash(self.mock_client, "consistency_msg_id_2")
        
        assert hash1 == hash2
        assert hash1 is not None

    def test_compute_canonical_hash_different_emails(self):
        """Test that different emails produce different canonical hashes."""
        email_content1 = """From: sender@example.com
To: recipient@example.com
Subject: First Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test1@example.com>

First message content."""
        
        email_content2 = """From: sender@example.com
To: recipient@example.com
Subject: Second Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test2@example.com>

Second message content."""
        
        # Setup first call
        raw_bytes1 = email_content1.encode('utf-8')
        raw_b64_1 = base64.urlsafe_b64encode(raw_bytes1).decode('utf-8')
        
        # Setup second call
        raw_bytes2 = email_content2.encode('utf-8')
        raw_b64_2 = base64.urlsafe_b64encode(raw_bytes2).decode('utf-8')
        
        self.mock_service.users().messages().get().execute.side_effect = [
            {'raw': raw_b64_1},
            {'raw': raw_b64_2}
        ]
        
        hash1, _ = compute_canonical_hash(self.mock_client, "different_msg_id_1")
        hash2, _ = compute_canonical_hash(self.mock_client, "different_msg_id_2")
        
        assert hash1 != hash2
        assert hash1 is not None
        assert hash2 is not None

    @patch('gmail_copy_tool.utils.canonicalization.logging.getLogger')
    def test_compute_canonical_hash_logging(self, mock_get_logger):
        """Test that appropriate logging occurs during hash computation."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Test successful case
        email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

Test body."""
        
        raw_bytes = email_content.encode('utf-8')
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode('utf-8')
        
        mock_response = {
            'raw': raw_b64
        }
        self.mock_service.users().messages().get().execute.return_value = mock_response
        
        compute_canonical_hash(self.mock_client, "log_test_msg_id")
        
        # Verify debug logging was called
        assert mock_logger.debug.called
        
        # Test error case
        self.mock_service.users().messages().get().execute.side_effect = Exception("Test error")
        
        compute_canonical_hash(self.mock_client, "error_msg_id")
        
        # Verify error logging was called
        assert mock_logger.error.called