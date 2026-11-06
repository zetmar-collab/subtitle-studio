from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDockWidget,QWidget,QVBoxLayout,QLabel,QPushButton,QComboBox


class WorkflowDock(QDockWidget):
    def __init__(self,workspace):
        super().__init__('Film → napisy → MP4',workspace)
        self.workspace=workspace
        body=QWidget();layout=QVBoxLayout(body);self.setWidget(body)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        for text,callback in [
            ('1. Wybierz film / Choose video',workspace.editor.open_video),
            ('2. Model i język / Model and language',self.settings),
            ('3. Transkrybuj / Transcribe',self.transcribe),
            ('4. Sprawdź tekst / Review transcript',workspace.show_review)]:
            button=QPushButton(text);button.clicked.connect(callback);layout.addWidget(button)
        self.style=QComboBox();self.style.addItems([item['name'] for item in workspace.editor.preset_data]);layout.addWidget(self.style)
        for text,callback in [('5. Przekaż i zastosuj styl / Transfer and style',self.apply_style),
                              ('6. Eksportuj film / Export video',workspace.editor.export_video)]:
            button=QPushButton(text);button.clicked.connect(callback);layout.addWidget(button)
        layout.addStretch();self.setMinimumWidth(300)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(500);self.refresh()

    def settings(self):
        self.workspace.speech();self.workspace.tabs.setCurrentIndex(1)

    def transcribe(self):
        self.workspace.transcribe_video()

    def apply_style(self):
        if self.workspace.send_to_editor():
            self.workspace.editor.apply_preset(self.style.currentIndex())

    def refresh(self):
        editor=self.workspace.editor;speech=self.workspace.transcription
        count=len(speech.project.segments) if speech else 0
        self.status.setText(f'Film / Video: {Path(editor.project.video).name if editor.project.video else "—"}\n'
            f'Transkrypcja / Transcript: {count}\n'
            'Przejdź etapy po kolei. Możesz wracać do edycji w obu kartach.\n'
            'Follow the steps; both editors remain available.')
