import os
import json
import threading

class Checkpoint:
    """Checkpoint manager for tracking copied Gmail message IDs."""
    def __init__(self, path):
        """Initialize checkpoint with file path."""
        self.path = path
        self._lock = threading.Lock()
        self._copied = set()
        self._load()

    def _load(self):
        """Load checkpoint data from file."""
        if not os.path.exists(self.path):
            self._copied = set()
            return
        try:
            with open(self.path, 'r') as f:
                data = json.load(f)
            self._copied = set(data.get('copied', []))
        except Exception:
            # Corrupted file: start fresh
            self._copied = set()

    def _save(self):
        """Save checkpoint data to file."""
        tmp_path = self.path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump({'copied': list(self._copied)}, f)
        os.replace(tmp_path, self.path)

    def mark_copied(self, msgid):
        """Mark a message ID as copied."""
        with self._lock:
            self._copied.add(msgid)
            self._save()

    def is_copied(self, msgid):
        """Return True if message ID has been copied."""
        with self._lock:
            return msgid in self._copied
