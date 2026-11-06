import multiprocessing as mp
import queue
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .engine import worker
from .paths import data_dir


class Job(QObject):
    event = Signal(object)
    finished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.timer = QTimer(self)
        self.timer.setInterval(70)
        self.timer.timeout.connect(self.poll)
        self.work = None
        self.success = False
        self.reported_error = False

    @property
    def active(self):
        return self.process is not None

    def start(self, kind, args, work_parent=None):
        if self.active:
            raise RuntimeError("busy")
        self.work = None
        self.queue = None
        self.success = False
        self.reported_error = False
        self.started = time.monotonic()
        try:
            self.work = Path(tempfile.mkdtemp(prefix="szept-work-", dir=work_parent or data_dir()))
            args = dict(args, work=str(self.work))
            ctx = mp.get_context("spawn")
            self.queue = ctx.Queue()
            self.process = ctx.Process(target=worker, args=(kind, args, self.queue), daemon=True)
            self.process.start()
            self.timer.start()
        except Exception as error:
            self.reported_error = True
            self.event.emit(('error',type(error).__name__,str(error)))
            self.cleanup()

    def poll(self):
        if not self.process:
            return
        current = self.process
        for _ in range(100):
            try:
                message = self.queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "done":
                self.success = True
            elif message[0] == "error":
                self.reported_error = True
            self.event.emit(message)
            if self.process is not current:
                return
        if not self.process.is_alive():
            self.process.join()
            # The queue feeder may flush its last messages just before process exit.
            while True:
                try:
                    message = self.queue.get_nowait()
                except queue.Empty:
                    break
                if message[0] == "done":
                    self.success = True
                elif message[0] == "error":
                    self.reported_error = True
                self.event.emit(message)
                if self.process is not current:
                    return
            if not self.success and not self.reported_error:
                self.event.emit(("error", "ProcessExit", str(self.process.exitcode)))
                if self.process is not current:
                    return
            self.cleanup()

    def cancel(self):
        if self.process:
            if self.process.is_alive():
                # taskkill /T also stops an active FFmpeg child before removing work files.
                if __import__("os").name == "nt":
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    self.process.terminate()
                self.process.join(timeout=5)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=5)
            self.success = False
            self.cleanup()

    def cleanup(self):
        self.timer.stop()
        if self.process:self.process.close()
        self.process = None
        if self.queue:self.queue.close()
        if self.work:shutil.rmtree(self.work, ignore_errors=True)
        self.finished.emit(self.success)
