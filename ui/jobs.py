from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QCoreApplication
import array
import subprocess
import threading
from core.media.tools import binary, FLAGS


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)

    def __init__(self, success, failure):
        # The application owns this receiver until the queued result is delivered.
        # QRunnable auto-deletion must not destroy its signals before the GUI reads them.
        super().__init__(QCoreApplication.instance())
        self.success = success
        self.failure = failure
        self.done.connect(self.deliver)
        self.error.connect(self.fail)

    @Slot(object)
    def deliver(self, result):
        try:
            self.success(result)
        finally:
            self.deleteLater()

    @Slot(str)
    def fail(self, message):
        try:
            self.failure(message)
        finally:
            self.deleteLater()


class Job(QRunnable):
    def __init__(self, function, done, error):
        super().__init__()
        self.function = function
        self.signals = Signals(done,error)

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as e:
            self.signals.error.emit(str(e))


def waveform(path, cancelled=lambda:False, start=0, duration=None):
    # Low sample rate and a bounded read prevent loading full-resolution PCM into memory.
    command=[binary('ffmpeg'),'-v','error','-nostdin']
    if start:command+=['-ss',str(start)]
    command+=['-i',str(path)]
    if duration is not None:command+=['-t',str(duration)]
    p = subprocess.Popen(command+['-vn',
                          '-af', 'aformat=channel_layouts=mono,aeval=abs(val(0))', '-ac', '1', '-ar', '100',
                          '-f', 's16le', 'pipe:1'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=FLAGS)
    stopped=threading.Event()
    def watch():
        while not stopped.wait(.1):
            if cancelled():
                if p.poll() is None:
                    try:p.kill()
                    except OSError:pass
                return
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    try:
        data = p.stdout.read(7_200_000)  # up to ten hours at 100 Hz
        if p.poll() is None:
            p.kill()
        p.wait()
        pcm = array.array('h', data[:len(data)//2*2])
        step = max(1, len(pcm)//1400)
        peaks = [max((abs(v)/32768 for v in pcm[i:i+step]), default=0) for i in range(0, len(pcm), step)]
        ceiling = max(peaks,default=0) or 1
        return [v/ceiling for v in peaks]
    finally:
        stopped.set()
        if p.poll() is None:
            p.kill()
            p.wait()
        watcher.join(timeout=1)
