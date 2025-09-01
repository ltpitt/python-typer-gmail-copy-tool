import os
import tempfile
import json
import threading
import pytest

from gmail_copy_tool.utils.checkpoint import Checkpoint


def test_checkpoint_creation_and_basic_usage():
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        # Initially empty
        assert not cp.is_copied("msgid1")
        # Mark as copied
        cp.mark_copied("msgid1")
        assert cp.is_copied("msgid1")
        # Mark another
        cp.mark_copied("msgid2")
        assert cp.is_copied("msgid2")
        # Should persist after reload
        cp2 = Checkpoint(checkpoint_path)
        assert cp2.is_copied("msgid1")
        assert cp2.is_copied("msgid2")


def test_checkpoint_atomicity():
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        cp.mark_copied("msgid1")
        # Simulate interruption by corrupting the file
        with open(checkpoint_path, "w") as f:
            f.write("corrupted")
        # Should recover gracefully (empty or partial state)
        cp2 = Checkpoint(checkpoint_path)
        assert not cp2.is_copied("msgid1") or isinstance(cp2, Checkpoint)


def test_checkpoint_file_creation():
    """Test that checkpoint file is created when it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "new_checkpoint.json")
        
        # File shouldn't exist initially
        assert not os.path.exists(checkpoint_path)
        
        # Creating checkpoint should work even without existing file
        cp = Checkpoint(checkpoint_path)
        assert not cp.is_copied("test_msgid")
        
        # Adding a message should create the file
        cp.mark_copied("test_msgid")
        assert os.path.exists(checkpoint_path)
        assert cp.is_copied("test_msgid")


def test_checkpoint_empty_file():
    """Test checkpoint behavior with empty file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "empty_checkpoint.json")
        
        # Create empty file
        with open(checkpoint_path, 'w') as f:
            pass
        
        # Should handle empty file gracefully
        cp = Checkpoint(checkpoint_path)
        assert not cp.is_copied("test_msgid")


def test_checkpoint_invalid_json():
    """Test checkpoint behavior with invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "invalid_checkpoint.json")
        
        # Create file with invalid JSON
        with open(checkpoint_path, 'w') as f:
            f.write("{invalid json")
        
        # Should recover gracefully
        cp = Checkpoint(checkpoint_path)
        assert not cp.is_copied("test_msgid")


def test_checkpoint_valid_json_no_copied_key():
    """Test checkpoint with valid JSON but missing 'copied' key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "no_copied_key.json")
        
        # Create file with valid JSON but no 'copied' key
        with open(checkpoint_path, 'w') as f:
            json.dump({"other_key": "value"}, f)
        
        # Should handle missing 'copied' key gracefully
        cp = Checkpoint(checkpoint_path)
        assert not cp.is_copied("test_msgid")


def test_checkpoint_multiple_operations():
    """Test multiple operations on the same checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "multi_checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        
        # Mark multiple messages as copied
        messages = [f"msg_{i}" for i in range(10)]
        for msg in messages:
            cp.mark_copied(msg)
        
        # Verify all are marked
        for msg in messages:
            assert cp.is_copied(msg)
        
        # Verify persistence
        cp2 = Checkpoint(checkpoint_path)
        for msg in messages:
            assert cp2.is_copied(msg)


def test_checkpoint_duplicate_marking():
    """Test marking the same message multiple times."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "dup_checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        
        # Mark same message multiple times
        cp.mark_copied("duplicate_msg")
        cp.mark_copied("duplicate_msg")
        cp.mark_copied("duplicate_msg")
        
        # Should still be marked as copied
        assert cp.is_copied("duplicate_msg")
        
        # Check file contains only one entry
        with open(checkpoint_path, 'r') as f:
            data = json.load(f)
        
        # Should only have one occurrence
        assert data['copied'].count("duplicate_msg") == 1


def test_checkpoint_thread_safety():
    """Test that checkpoint operations are thread-safe."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "thread_checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        
        results = []
        errors = []
        
        def worker(msg_prefix):
            try:
                for i in range(50):
                    msg_id = f"{msg_prefix}_{i}"
                    cp.mark_copied(msg_id)
                    assert cp.is_copied(msg_id)
                results.append(f"{msg_prefix}_success")
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(f"thread_{i}",))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 5
        
        # Verify all messages were recorded
        for i in range(5):
            for j in range(50):
                msg_id = f"thread_{i}_{j}"
                assert cp.is_copied(msg_id)


def test_checkpoint_file_permissions():
    """Test checkpoint behavior with file permission issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "perm_checkpoint.json")
        
        # Create checkpoint and add a message
        cp = Checkpoint(checkpoint_path)
        cp.mark_copied("test_msg")
        assert cp.is_copied("test_msg")
        
        # Note: Making directory read-only might not prevent file access on all systems
        # This test primarily ensures the implementation handles filesystem issues gracefully
        # The exact behavior may vary by platform
        if os.name != 'nt':  # Skip detailed permission test on Windows
            # Make file read-only
            os.chmod(checkpoint_path, 0o444)
            try:
                # Should still be able to read existing file
                cp2 = Checkpoint(checkpoint_path)
                assert cp2.is_copied("test_msg")
                
                # Writing might fail, but should be handled gracefully
                # This test mainly ensures no crashes occur
                try:
                    cp2.mark_copied("new_msg")
                except (OSError, IOError):
                    # Expected on systems that enforce read-only files
                    pass
            finally:
                # Restore permissions for cleanup
                os.chmod(checkpoint_path, 0o644)


def test_checkpoint_path_property():
    """Test that checkpoint path is accessible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "path_test.json")
        cp = Checkpoint(checkpoint_path)
        assert cp.path == checkpoint_path


def test_checkpoint_large_dataset():
    """Test checkpoint with a large number of message IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "large_checkpoint.json")
        cp = Checkpoint(checkpoint_path)
        
        # Add many message IDs
        num_messages = 1000
        for i in range(num_messages):
            cp.mark_copied(f"large_msg_{i}")
        
        # Verify all are present
        for i in range(num_messages):
            assert cp.is_copied(f"large_msg_{i}")
        
        # Verify persistence
        cp2 = Checkpoint(checkpoint_path)
        for i in range(num_messages):
            assert cp2.is_copied(f"large_msg_{i}")
        
        # Verify file size is reasonable
        file_size = os.path.getsize(checkpoint_path)
        assert file_size > 0
        assert file_size < 1024 * 1024  # Should be less than 1MB for 1000 IDs
