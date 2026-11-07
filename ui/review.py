from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
                              QPushButton,QCheckBox,QAbstractItemView)
from srtstudio.project import timestamp


def reasons(segment):
    result=[]
    if segment.review:result.append('ASR: do sprawdzenia / review')
    if not segment.words:result.append('Brak czasów słów / No word timing')
    scores=[word['probability'] for word in segment.words if 'probability' in word]
    if scores and min(scores)<.6:result.append(f'Słaba ocena słów / Low word score: {min(scores):.2f}')
    return result


class ReviewDialog(QDialog):
    def __init__(self,workspace):
        super().__init__(workspace)
        from ui.help import install_help
        install_help(self, workspace.editor)
        self.workspace=workspace;self.speech=workspace.speech();self.signature=None
        self.setWindowTitle('Fragmenty do sprawdzenia / Review queue');self.resize(900,500)
        layout=QVBoxLayout(self);note=QLabel('Oceny ASR są przybliżone. Kliknij fragment, popraw tekst w karcie Transkrypcja i odsłuchaj.\n'
            'ASR scores are approximate. Select a fragment, edit in the Transcription tab and listen.')
        note.setWordWrap(True);layout.addWidget(note)
        self.show_checked=QCheckBox('Pokaż sprawdzone / Include reviewed');layout.addWidget(self.show_checked)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Nr','Czas / Time','Powód / Reason','Tekst / Text'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        bar=QHBoxLayout();layout.addLayout(bar)
        for label,callback in [('Odsłuch / Listen',self.listen),('Sprawdzono / Mark reviewed',lambda:self.mark(True)),
                               ('Cofnij oznaczenie / Unmark',lambda:self.mark(False))]:
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button)
        self.table.itemSelectionChanged.connect(self.select)
        self.show_checked.toggled.connect(lambda:self.refresh(force=True))
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(500);self.refresh()

    def refresh(self,force=False):
        data=[(s.start,s.end,s.text,s.review,s.checked,tuple(reasons(s))) for s in self.speech.project.segments]
        signature=(id(self.speech.project),data,self.show_checked.isChecked())
        if not force and self.signature==signature:return
        self.signature=signature
        self.indices=[i for i,s in enumerate(self.speech.project.segments)
                      if reasons(s) and (self.show_checked.isChecked() or not s.checked)]
        self.table.blockSignals(True);self.table.setRowCount(len(self.indices))
        for row,index in enumerate(self.indices):
            s=self.speech.project.segments[index]
            for col,value in enumerate([str(index+1),timestamp(s.start),'; '.join(reasons(s)),('✓ ' if s.checked else '')+s.text]):
                self.table.setItem(row,col,QTableWidgetItem(value))
        self.table.blockSignals(False)

    def current(self):
        row=self.table.currentRow()
        return self.indices[row] if 0<=row<len(self.indices) else None

    def select(self):
        index=self.current()
        if index is not None:
            self.workspace.tabs.setCurrentIndex(1);self.speech.table.selectRow(index)

    def listen(self):
        if self.current() is not None:
            self.select();self.speech.listen_segment()

    def mark(self,value):
        if self.speech.job.active:return
        index=self.current()
        if index is not None:
            self.speech.project.segments[index].checked=value
            self.speech.record();self.speech.render();self.speech.autosave();self.refresh(force=True)
