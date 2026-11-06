from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QFileDialog, QComboBox, QDoubleSpinBox
from ui.media_job import MediaJobDialog


class JoinDialog(MediaJobDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(parent.tr_text('Połącz filmy', 'Join videos'))
        self.resize(680,500)
        layout = self.body_layout
        text = parent.tr_text('Kolejność od góry. Dopasowanie obrazu z pasami. Pierwsza ścieżka audio każdego filmu; cisza przy braku dźwięku.',
                              'Top-to-bottom order. Fit with bars. First audio track per video; silence when audio is missing.')
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.files = QListWidget()
        layout.addWidget(self.files)
        self.controls = []
        buttons = QHBoxLayout()
        for pl,en,callback in [('Dodaj filmy','Add videos',self.add_files),('W górę','Move up',lambda: self.move(-1)),
                               ('W dół','Move down',lambda: self.move(1)),('Usuń','Remove',self.remove)]:
            button = QPushButton(parent.tr_text(pl,en))
            button.clicked.connect(callback)
            buttons.addWidget(button)
            self.controls.append(button)
        layout.addLayout(buttons)
        self.size_combo = QComboBox()
        self.size_combo.addItems(['1920 × 1080','1080 × 1920','1080 × 1080','640 × 360'])
        self.fps = QDoubleSpinBox()
        self.fps.setRange(1,120)
        self.fps.setDecimals(3)
        self.fps.setValue(30)
        self.fps.setSuffix(' FPS')
        profiles = QHBoxLayout()
        profiles.addWidget(self.size_combo)
        profiles.addWidget(self.fps)
        self.controls.extend([self.size_combo,self.fps,self.files])
        layout.addLayout(profiles)
        self.add_job_controls(parent.tr_text('Połącz i zapisz MP4','Join and save MP4'))

    def add_files(self):
        paths,_ = QFileDialog.getOpenFileNames(self,self.windowTitle(),'','Video (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.mts *.ts);;All (*)')
        self.files.addItems(paths)

    def move(self, direction):
        row = self.files.currentRow()
        if row >= 0 and 0 <= row+direction < self.files.count():
            item = self.files.takeItem(row)
            self.files.insertItem(row+direction,item)
            self.files.setCurrentRow(row+direction)

    def remove(self):
        row = self.files.currentRow()
        if row >= 0:
            self.files.takeItem(row)

    def begin(self):
        if not 2 <= self.files.count() <= 40:
            self.message.setText(self.owner.tr_text('Wybierz od 2 do 40 filmów.','Choose 2 to 40 videos.'))
            return
        target = self.choose_target()
        if not target:
            return
        width,height = [(1920,1080),(1080,1920),(1080,1080),(640,360)][self.size_combo.currentIndex()]
        job = dict(paths=[self.files.item(i).text() for i in range(self.files.count())],target=target,
                   options=dict(width=width,height=height,fps=self.fps.value()))
        self.start_job('--join',job,target)
