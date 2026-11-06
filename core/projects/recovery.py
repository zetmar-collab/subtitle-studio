"""Recovery files belong to a live session, never to another window/process."""
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QLockFile


class RecoverySession:
    def __init__(self, folder, prefix, legacy):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.prefix = prefix
        self.legacy = self.folder / legacy
        self.path = self.folder / f'{prefix}-{uuid4().hex}.autosave.json'
        self.lock = QLockFile(str(self.path) + '.lock')
        self.claims = []
        if not self.lock.tryLock(0):
            raise OSError('Nie można zablokować sesji odzyskiwania / Cannot lock recovery session')

    def candidates(self):
        files = list(self.folder.glob(f'{self.prefix}-*.autosave.json'))
        if self.legacy.exists():
            files.append(self.legacy)
        available = []
        for path in files:
            if path == self.path:
                continue
            lock = QLockFile(str(path) + '.lock')
            if lock.tryLock(0):
                available.append(path)
                lock.unlock()
        return sorted(available, key=lambda path: path.stat().st_mtime, reverse=True)

    def close(self):
        self.path.unlink(missing_ok=True)
        self.discard_claims()
        self.lock.unlock()

    def claim(self,path):
        path=Path(path)
        if path not in self.candidates():return False
        lock=QLockFile(str(path)+'.lock')
        if not lock.tryLock(0):return False
        self.claims.append((path,lock));return True

    def discard_claims(self):
        for path,lock in self.claims:
            path.unlink(missing_ok=True);lock.unlock()
        self.claims.clear()
