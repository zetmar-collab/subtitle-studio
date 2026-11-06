from pathlib import Path
from PySide6.QtWidgets import (QTableWidget,QTableWidgetItem,QPushButton,QHBoxLayout,QLabel,
                              QFileDialog,QLineEdit,QComboBox,QDoubleSpinBox,QCheckBox)
from ui.media_job import MediaJobDialog


class SlideshowDialog(MediaJobDialog):
    def __init__(self,owner):
        super().__init__(owner);self.setWindowTitle('Pokaz zdjęć i klipów / Slideshow');self.resize(850,650)
        layout=self.body_layout
        layout.addWidget(QLabel('Kolejność od góry. Dźwięk klipów zastępuje wybrane audio. / Top-to-bottom; selected audio replaces clip sound.'))
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['Obraz / Visual','Czas / Seconds'])
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        bar=QHBoxLayout();layout.addLayout(bar)
        for label,callback in [('Dodaj / Add',self.add),('Usuń / Remove',self.remove),('↑',lambda:self.move(-1)),('↓',lambda:self.move(1))]:
            button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button);self.controls.append(button)
        self.audio_path=QLineEdit();self.audio_path.setReadOnly(True)
        button=QPushButton('Wybierz audio / Choose audio');button.clicked.connect(self.audio)
        bar=QHBoxLayout();bar.addWidget(self.audio_path);bar.addWidget(button);layout.addLayout(bar);self.controls.append(button)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.size=QComboBox();self.size.addItems(['1920×1080','1080×1920','1080×1080','1080×1350','1440×1080','640×360'])
        self.fps=QDoubleSpinBox();self.fps.setRange(1,120);self.fps.setValue(30);self.fps.setSuffix(' FPS')
        self.fit=QComboBox();self.fit.addItems(['Dopasuj / Fit','Przytnij / Crop'])
        for widget in (self.size,self.fps,self.fit):bar.addWidget(widget);self.controls.append(widget)
        self.automatic=QCheckBox('Dopasuj czasy zdjęć do audio (tylko zdjęcia) / Fit photo durations to audio');self.automatic.setChecked(True)
        self.fade=QCheckBox('Przejścia przez czerń / Fade through black')
        self.motion=QCheckBox('Delikatne przybliżenie zdjęć / Slow photo zoom')
        for widget in (self.automatic,self.fade,self.motion):layout.addWidget(widget);self.controls.append(widget)
        self.length=QComboBox();self.length.addItems(['Powtarzaj pokaz do końca audio / Loop to audio end',
            'Zatrzymaj ostatnią klatkę / Freeze last frame','Krótszy materiał / Shortest'])
        layout.addWidget(self.length);self.controls.extend([self.length,self.table])
        self.add_job_controls('Utwórz pokaz / Create slideshow')

    def add(self):
        paths,_=QFileDialog.getOpenFileNames(self,self.windowTitle(),'',
            'Visuals (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.avi *.webm);;All (*)')
        for path in paths:
            row=self.table.rowCount();self.table.insertRow(row)
            self.table.setItem(row,0,QTableWidgetItem(path));self.table.setItem(row,1,QTableWidgetItem('3'))

    def remove(self):
        row=self.table.currentRow()
        if row>=0:self.table.removeRow(row)

    def move(self,direction):
        row=self.table.currentRow();target=row+direction
        if 0<=row<self.table.rowCount() and 0<=target<self.table.rowCount():
            first=[self.table.takeItem(row,col) for col in range(2)];second=[self.table.takeItem(target,col) for col in range(2)]
            for col in range(2):self.table.setItem(row,col,second[col]);self.table.setItem(target,col,first[col])
            self.table.selectRow(target)

    def audio(self):
        path,_=QFileDialog.getOpenFileName(self,self.windowTitle(),'','Audio (*.wav *.mp3 *.m4a *.flac *.aac *.ogg *.opus);;All (*)')
        if path:self.audio_path.setText(path)

    def begin(self):
        try:
            clips=[dict(path=self.table.item(row,0).text(),seconds=float(self.table.item(row,1).text())) for row in range(self.table.rowCount())]
            if not clips or not self.audio_path.text():raise ValueError('Dodaj obrazy i audio / Add visuals and audio')
            target=self.choose_target()
            if not target:return
            width,height=map(int,self.size.currentText().split('×'))
            options=dict(width=width,height=height,fps=self.fps.value(),fit='fit' if self.fit.currentIndex()==0 else 'crop',
                         auto_duration=self.automatic.isChecked(),fade=self.fade.isChecked(),motion=self.motion.isChecked(),
                         length=['loop','freeze','shortest'][self.length.currentIndex()])
            self.start_job('--slideshow',dict(clips=clips,audio=self.audio_path.text(),target=target,options=options),target)
        except ValueError as error:self.message.setText(str(error))
