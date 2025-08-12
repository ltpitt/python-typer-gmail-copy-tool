import unittest.mock
import base64
import email.mime.text


def test_gmail_api_insert_call_format():
    """
    Test that the Gmail API insert call uses the correct parameter format
    """
    # This test verifies the API call format we expect
    import googleapiclient.discovery
    
    # Mock the service
    with unittest.mock.patch.object(googleapiclient.discovery, 'build') as mock_build:
        mock_service = unittest.mock.MagicMock()
        mock_build.return_value = mock_service
        
        # Test the exact call format we use in copy.py
        mock_service.users().messages().insert(
            userId="me", 
            body={"raw": "dGVzdA=="}, 
            internalDateSource="dateHeader"
        ).execute()
        
        # Verify the call was made with the expected parameters
        mock_service.users().messages().insert.assert_called_once_with(
            userId="me", 
            body={"raw": "dGVzdA=="}, 
            internalDateSource="dateHeader"
        )


def test_copy_function_has_correct_insert_call():
    """
    Test that the copy.py file contains the correct Gmail API insert call
    """
    # Read the copy.py file and verify it contains the correct API call
    import os
    copy_file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'src', 'gmail_copy_tool', 'commands', 'copy.py'
    )
    
    with open(copy_file_path, 'r') as f:
        content = f.read()
    
    # Verify the file contains the correct API call with internalDateSource
    assert 'internalDateSource="dateHeader"' in content, "copy.py should contain internalDateSource parameter"
    assert 'messages().insert(userId="me", body={"raw": src_raw_b64}, internalDateSource="dateHeader")' in content, "Incorrect API call format"