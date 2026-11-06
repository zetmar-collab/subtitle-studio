from pathlib import Path
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
                               QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox)
from core.media.create_video import thumbnail, IMAGE_EXTENSIONS
from ui.jobs import Job
from ui.media_job import MediaJobDialog


class CreateVideoDialog(MediaJobDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(parent.tr_text('Film z obrazu i audio','Video from image and audio'))
        self.resize(740,760)
        self.frame = QImage()
        self.preview_request = 0
        self.finished.connect(self.invalidate_preview)
        form = QFormLayout()
        self.body_layout.addLayout(form)
        self.visual_path = QLineEdit()
        self.visual_path.setReadOnly(True)
        self.audio_path = QLineEdit()
        self.audio_path.setReadOnly(True)
        for field,pl,en,callback in [(self.visual_path,'Zdjęcie lub film','Image or video',self.choose_visual),
                                     (self.audio_path,'Osobny dźwięk','Separate audio',self.choose_audio)]:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(field)
            button = QPushButton(parent.tr_text('Wybierz…','Choose…'))
            button.clicked.connect(callback)
            layout.addWidget(button)
            self.controls.extend([field,button])
            form.addRow(parent.tr_text(pl,en),row)

        self.profiles = [
            ('16:9 · 1920 × 1080',1920,1080),
            ('16:9 · 1280 × 720',1280,720),
            ('16:9 · 4K · 3840 × 2160',3840,2160),
            ('9:16 · 1080 × 1920',1080,1920),
            ('1:1 · 1080 × 1080',1080,1080),
            ('4:5 · 1080 × 1350',1080,1350),
            ('4:3 · 1440 × 1080',1440,1080),
            (parent.tr_text('Własny rozmiar','Custom size'),None,None),
        ]
        self.profile = QComboBox()
        self.profile.addItems([entry[0] for entry in self.profiles])
        form.addRow(parent.tr_text('Format obrazu','Frame format'),self.profile)
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box,value in [(self.width_box,1920),(self.height_box,1080)]:
            box.setRange(2,7680)
            box.setSingleStep(2)
            box.setValue(value)
            box.setSuffix(' px')
            box.setEnabled(False)
            box.valueChanged.connect(self.update_preview)
        dimensions = QHBoxLayout()
        dimensions.addWidget(self.width_box)
        dimensions.addWidget(QLabel('×'))
        dimensions.addWidget(self.height_box)
        form.addRow(parent.tr_text('Wymiary','Dimensions'),dimensions)
        self.profile.currentIndexChanged.connect(self.profile_changed)
        self.fit_mode = QComboBox()
        self.fit_mode.addItems([parent.tr_text('Cały obraz z pasami','Fit entire image with bars'),
                                parent.tr_text('Wypełnij kadr — przytnij środek','Fill frame — crop center')])
        self.fit_mode.currentIndexChanged.connect(self.update_preview)
        form.addRow(parent.tr_text('Dopasowanie','Framing'),self.fit_mode)
        self.length_mode = QComboBox()
        self.length_mode.addItems([parent.tr_text('Długość audio — powtarzaj film','Audio duration — loop video'),
                                   parent.tr_text('Długość audio — zatrzymaj ostatnią klatkę','Audio duration — freeze last frame'),
                                   parent.tr_text('Krótszy z plików','Shorter of the two files')])
        form.addRow(parent.tr_text('Długość dla wideo','Video duration'),self.length_mode)
        self.fps = QDoubleSpinBox()
        self.fps.setRange(1,120)
        self.fps.setDecimals(3)
        self.fps.setValue(30)
        self.crf = QSpinBox()
        self.crf.setRange(0,51)
        self.crf.setValue(20)
        form.addRow('FPS',self.fps)
        form.addRow('CRF',self.crf)
        self.controls.extend([self.profile,self.fit_mode,self.length_mode,self.fps,self.crf])
        note = QLabel(parent.tr_text(
            'Dźwięk wyniku pochodzi z wybranego pliku audio. Zdjęcie jest widoczne przez całą długość audio. Podgląd pokazuje zdjęcie lub pierwszą klatkę filmu.',
            'Output sound comes from the selected audio file. A photo stays visible for the full audio duration. Preview shows the photo or the first video frame.'))
        note.setWordWrap(True)
        self.body_layout.addWidget(note)
        self.preview_label = QLabel(parent.tr_text('Wybierz zdjęcie lub film, aby zobaczyć kadr.','Choose an image or video to preview framing.'))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        self.preview_label.setStyleSheet('background:#101218; border:1px solid #48536a; border-radius:6px;')
        self.body_layout.addWidget(self.preview_label)
        self.add_job_controls(parent.tr_text('Utwórz i zapisz MP4','Create and save MP4'))

    def choose_visual(self):
        path,_ = QFileDialog.getOpenFileName(self,self.windowTitle(),'',
            'Images and video (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.avi *.webm *.wmv *.mpeg *.mpg *.m4v *.mts *.ts);;All (*)')
        if path:
            self.set_visual(path)

    def set_visual(self, path):
        self.message.clear()
        self.visual_path.setText(str(path))
        self.visual_path.setToolTip(str(path))
        self.frame = QImage()
        self.preview_label.clear()
        self.preview_label.setText(self.owner.tr_text('Ładowanie podglądu…','Loading preview…'))
        self.update_preview()
        self.length_mode.setEnabled(Path(path).suffix.lower() not in IMAGE_EXTENSIONS)
        self.preview_request += 1
        request = self.preview_request
        def ready(frame):
            if request == self.preview_request:
                self.frame = frame
                self.update_preview()
        def failed(error):
            if request == self.preview_request:
                self.message.setText(error)
        self.owner.pool.start(Job(lambda: thumbnail(path),ready,failed))

    def invalidate_preview(self, result):
        self.preview_request += 1

    def choose_audio(self):
        path,_ = QFileDialog.getOpenFileName(self,self.windowTitle(),'',
            'Audio (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma);;All (*)')
        if path:
            self.audio_path.setText(path)
            self.audio_path.setToolTip(path)

    def profile_changed(self, index):
        _,width,height = self.profiles[index]
        custom = width is None
        self.width_box.setEnabled(custom and not self.process)
        self.height_box.setEnabled(custom and not self.process)
        if not custom:
            self.width_box.setValue(width)
            self.height_box.setValue(height)
        self.update_preview()

    def update_preview(self):
        if not hasattr(self,'preview_label') or self.frame.isNull():
            return
        size = QSize(self.width_box.value(),self.height_box.value()).scaled(560,240,Qt.AspectRatioMode.KeepAspectRatio)
        output = QImage(size,QImage.Format.Format_RGB888)
        output.fill(Qt.GlobalColor.black)
        mode = Qt.AspectRatioMode.KeepAspectRatio if self.fit_mode.currentIndex() == 0 else Qt.AspectRatioMode.KeepAspectRatioByExpanding
        scaled = self.frame.size().scaled(size,mode)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRectF((size.width()-scaled.width())/2,(size.height()-scaled.height())/2,
                                 scaled.width(),scaled.height()),self.frame)
        painter.end()
        self.preview_label.setPixmap(QPixmap.fromImage(output))

    def begin(self):
        visual, audio = self.visual_path.text(), self.audio_path.text()
        if not visual or not audio:
            self.message.setText(self.owner.tr_text('Wybierz obraz i osobny plik audio.','Choose a visual source and a separate audio file.'))
            return
        width, height = self.width_box.value(), self.height_box.value()
        if width % 2 or height % 2:
            self.message.setText(self.owner.tr_text('Wymiary muszą być parzyste.','Dimensions must be even.'))
            return
        target = self.choose_target()
        if not target:
            return
        options = dict(width=width,height=height,fps=self.fps.value(),crf=self.crf.value(),
                       fit=['fit','crop'][self.fit_mode.currentIndex()],
                       length=['loop','freeze','shortest'][self.length_mode.currentIndex()])
        job = dict(visual=visual,audio=audio,target=target,options=options)
        self.start_job('--create-video',job,target)
        self.width_box.setEnabled(False)
        self.height_box.setEnabled(False)

    def finish_job(self, code, exit_status):
        super().finish_job(code,exit_status)
        self.profile_changed(self.profile.currentIndex())
        self.length_mode.setEnabled(Path(self.visual_path.text()).suffix.lower() not in IMAGE_EXTENSIONS)
