from PySide6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
                              QDialogButtonBox,QSpinBox,QFormLayout)
from core.subtitles.repair import propose
from core.subtitles.service import warnings


class RepairDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.setWindowTitle('Naprawa synchronizacji / Repair timing');self.resize(850,550)
        layout=QVBoxLayout(self)
        note=QLabel('Propozycja zachowuje cały tekst. Zmienione granice unieważnią czasy słów.\n'
                    'The proposal keeps all text. Changed boundaries invalidate word alignment.')
        note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();self.minimum=QSpinBox();self.minimum.setRange(1,7000);self.minimum.setValue(600)
        form.addRow('Minimalny czas / Minimum (ms)',self.minimum);layout.addLayout(form)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Tekst / Text','Przed / Before','Po / After','Słowa / Words','Kontrola / Checks'])
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
        self.minimum.valueChanged.connect(self.refresh);self.refresh()

    def refresh(self):
        try:
            self.result=propose(self.owner.track().segments,self.owner.info['duration'],self.minimum.value())
            checks=warnings(self.result,self.owner.info['duration'],**self.owner.project.quality)
            before=sorted(self.owner.track().segments,key=lambda s:s.start)
            self.table.setRowCount(len(self.result))
            for row,(old,new) in enumerate(zip(before,self.result)):
                for col,value in enumerate([new.text,f'{old.start}–{old.end}',f'{new.start}–{new.end}',
                                           '✓' if new.words else '—',checks[row]]):
                    self.table.setItem(row,col,QTableWidgetItem(value))
            self.status.setText('Pozostałe uwagi czytelności wymagają sprawdzenia. / Review remaining readability warnings.')
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)
        except ValueError as error:
            self.status.setText(str(error));self.buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)

    def apply(self):
        self.owner.checkpoint();self.owner.track().segments=self.result;self.owner.refresh();self.accept()
