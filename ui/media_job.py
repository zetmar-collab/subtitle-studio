"""Shared lifecycle for local media generation dialogs."""
import json
from pathlib import Path
import sys
import tempfile
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QProgressBar


class MediaJobDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.owner = parent
        self.process = None
        self.temp = None
        self.target = None
        self.controls = []
        self.body_layout = QVBoxLayout(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(250)

    def add_job_controls(self, start_text):
        self.progress = QProgressBar()
        self.body_layout.addWidget(self.progress)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.body_layout.addWidget(self.message)
        bottom = QHBoxLayout()
        self.start = QPushButton(start_text)
        self.start.clicked.connect(self.begin)
        self.controls.append(self.start)
        bottom.addWidget(self.start)
        self.cancel = QPushButton(self.owner.tr_text('Anuluj zadanie','Cancel job'))
        self.cancel.clicked.connect(self.cancel_job)
        self.cancel.setEnabled(False)
        bottom.addWidget(self.cancel)
        self.open_button = QPushButton(self.owner.tr_text('Otwórz wynik w edytorze','Open result in editor'))
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_result)
        bottom.addWidget(self.open_button)
        self.body_layout.addLayout(bottom)

    def choose_target(self):
        target,_ = QFileDialog.getSaveFileName(self,self.windowTitle(),'','MP4 (*.mp4)')
        if not target:
            return None
        if not Path(target).suffix:
            target += '.mp4'
        if Path(target).suffix.lower() != '.mp4':
            self.message.setText(self.owner.tr_text('Wybierz rozszerzenie .mp4.','Choose the .mp4 extension.'))
            return None
        originals = [self.owner.project.video] + [logo.path for logo in self.owner.project.logos]
        originals += [track.source for track in self.owner.project.tracks]
        if any(path and Path(path).resolve() == Path(target).resolve() for path in originals):
            self.message.setText(self.owner.tr_text('Wybierz nowy plik, aby zachować oryginał.', 'Choose a new file to preserve the original.'))
            return None
        return target

    def start_job(self, mode, job, target):
        if self.process:
            return
        self.temp = tempfile.TemporaryDirectory(prefix='subtitle-media-job-')
        folder = Path(self.temp.name)
        self.status = folder/'status.json'
        self.cancel_path = folder/'cancel'
        config = folder/'job.json'
        config.write_text(json.dumps(job),encoding='utf-8')
        self.target = target
        self.progress.setValue(0)
        self.open_button.setEnabled(False)
        self.cancel.setEnabled(True)
        for widget in self.controls:
            widget.setEnabled(False)
        self.message.setText(self.owner.tr_text('Tworzenie filmu w osobnym procesie…','Creating video in a separate process…'))
        self.process = QProcess(self)
        self.process.finished.connect(self.finish_job)
        self.process.errorOccurred.connect(self.process_error)
        args = [mode,str(config),str(self.cancel_path),str(self.status)]
        if not getattr(sys,'frozen',False):
            args.insert(0,str(Path(__file__).resolve().parents[1]/'main.py'))
        self.process.start(sys.executable,args)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.process:
            self.finish_job(1,QProcess.ExitStatus.CrashExit)

    def read_status(self):
        try:
            return json.loads(self.status.read_text(encoding='utf-8'))
        except (OSError,ValueError,AttributeError):
            return {}

    def poll(self):
        if self.process:
            self.progress.setValue(self.read_status().get('percent',self.progress.value()))

    def finish_job(self, code, exit_status):
        status = self.read_status()
        success = code == 0 and status.get('done')
        self.message.setText(self.owner.tr_text('Film gotowy i sprawdzony.','Video ready and verified.') if success
                             else status.get('error',self.owner.tr_text('Błąd tworzenia filmu.','Video creation failed.')))
        self.progress.setValue(100 if success else self.progress.value())
        self.open_button.setEnabled(bool(success))
        self.cancel.setEnabled(False)
        for widget in self.controls:
            widget.setEnabled(True)
        self.process.deleteLater()
        self.process = None
        self.temp.cleanup()
        self.temp = None

    def cancel_job(self):
        if self.process:
            self.cancel_path.touch()
            self.message.setText(self.owner.tr_text('Anulowanie…','Cancelling…'))

    def open_result(self):
        if self.target and self.owner.new_project():
            self.owner.open_video(self.target)
            self.accept()

    def reject(self):
        if self.process:
            self.cancel_job()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.process:
            self.cancel_job()
            event.ignore()
        else:
            super().closeEvent(event)
