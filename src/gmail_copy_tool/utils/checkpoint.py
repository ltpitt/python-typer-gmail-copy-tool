import os
import json
import threading

class Checkpoint:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._copied = set()
        self._load()

    def _load(self):
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
        tmp_path = self.path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump({'copied': list(self._copied)}, f)
        os.replace(tmp_path, self.path)

    def mark_copied(self, msgid):
        with self._lock:
            self._copied.add(msgid)
            self._save()

    def is_copied(self, msgid):
        with self._lock:
            return msgid in self._copied
