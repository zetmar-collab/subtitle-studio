from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDockWidget,QWidget,QVBoxLayout,QLabel,QPushButton,QComboBox,QScrollArea


class WorkflowDock(QDockWidget):
    def __init__(self,workspace):
        super().__init__(workspace)
        self.workspace=workspace
        body=QWidget();layout=QVBoxLayout(body)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(body);self.setWidget(scroll)
        self.buttons=[]
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        for text,callback in [
            ('1. Otwórz film / Choose video',workspace.editor.open_video),
            ('2. Język i rozpoznawanie / Model and language',self.settings),
            ('3. Rozpoznaj mowę / Transcribe',self.transcribe),
            ('4. Sprawdź tekst / Review transcript',workspace.show_review)]:
            button=QPushButton();button.clicked.connect(callback);layout.addWidget(button)
            pl,en=text.split(" / ",1);self.buttons.append((button,pl,en))
        self.style=QComboBox();self.style.addItems([item['name'] for item in workspace.editor.preset_data]);layout.addWidget(self.style)
        for text,callback in [('5. Zastosuj napisy i styl / Transfer and style',self.apply_style),
                              ('6. Zapisz gotowy film / Export video',workspace.editor.export_video)]:
            button=QPushButton();button.clicked.connect(callback);layout.addWidget(button)
            pl,en=text.split(" / ",1);self.buttons.append((button,pl,en))
        layout.addStretch();self.setMinimumWidth(230)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(500);self.refresh()

    def settings(self):
        self.workspace.speech();self.workspace.tabs.setCurrentIndex(1)

    def transcribe(self):
        self.workspace.transcribe_video()

    def apply_style(self):
        if self.workspace.send_to_editor():
            self.workspace.editor.apply_preset(self.style.currentIndex())

    def refresh(self):
        self.workspace.refresh_actions()
        editor=self.workspace.editor;speech=self.workspace.transcription
        count=len(speech.project.segments) if speech else 0
        t=editor.tr_text
        self.setWindowTitle(t('Krok po kroku','Step by step'))
        has_video=bool(editor.project.video)
        busy=bool(editor.export_process or (speech and speech.job.active))
        self.status.setText(t('Film: ','Video: ')+(Path(editor.project.video).name if has_video else t('jeszcze nie wybrano','not selected'))+'\n'+t('Rozpoznane napisy: ','Recognized captions: ')+str(count))
        self.style.setAccessibleName(t('Styl napisów','Caption style'))
        for index,preset in enumerate(editor.preset_data):
            names=preset['name'].split(' / ',1)
            self.style.setItemText(index,names[0] if editor.project.language=='pl' else names[-1])
        for index,(button,pl,en) in enumerate(self.buttons):
            button.setText(t(pl,en))
            ready=not busy and (index==0 or has_video)
            if index in (3,4):ready=ready and count>0
            button.setEnabled(ready)
            button.setToolTip('' if ready else t('Najpierw wybierz film, rozpoznaj mowę lub poczekaj na koniec zadania.','Choose a video, recognize speech or wait for the current task first.'))
            current=0 if not has_video else (2 if not count else (4 if not editor.project.linked_track else 5))
            name='primary' if index==current else ''
            if button.objectName()!=name:
                button.setObjectName(name);button.style().unpolish(button);button.style().polish(button)
