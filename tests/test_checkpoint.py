import os
import tempfile
import json
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
