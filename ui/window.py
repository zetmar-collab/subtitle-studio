import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from PySide6.QtCore import Qt, QUrl, QTimer, QProcess, QThreadPool, QStandardPaths, QTranslator, QCoreApplication, QRectF, QLibraryInfo
from PySide6.QtGui import QAction, QKeySequence, QImage, QColor, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QPushButton, QLabel, QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox, QInputDialog,
    QSlider, QDialog, QDialogButtonBox, QProgressBar, QGroupBox, QScrollArea, QTextEdit, QColorDialog)
from core.projects.model import Project, Track, Segment, Logo, Style, save, load
from core.subtitles.service import read, write, shift, stretch, warnings
from core.media.tools import probe
from core.compositor.render import image, visible_text
from core.spellcheck.service import Spellchecker
from ui.preview import Preview, Timeline
from ui.jobs import Job, waveform
from ui.colors import ColorButton
from core.version import VERSION

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.catalog = {language: json.loads((ROOT/f'assets/i18n/{language}.json').read_text(encoding='utf-8')) for language in ('pl','en')}
        self.path = None
        self.dirty = False
        self.history = []
        self.future = []
        self.loading = False
        self._color_session = False
        self.info = dict(width=1920, height=1080, duration=0, fps=25)
        self.export_process = None
        self.export_temp = None
        self.active_track = 0
        self.active_logo = -1
        self.translated = []
        self.store = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.store.mkdir(parents=True, exist_ok=True)
        self.autopath = self.store/'recovery.autosave.json'
        self.spell = Spellchecker(self.store/'dictionaries', ROOT/'assets/dictionaries')
        self.pool = QThreadPool.globalInstance()
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self.video_frame)
        self.player.positionChanged.connect(self.position)
        self.player.errorOccurred.connect(lambda *a: self.statusBar().showMessage(self.player.errorString(), 15000))
        self.setWindowTitle('Subtitle Studio')
        self.setWindowIcon(QIcon(str(ROOT/'assets/icon.ico')))
        self.resize(1480, 940)
        self.setAcceptDrops(True)
        self.build()
        self.refresh()
        self.apply_theme()
        self.autotimer = QTimer(self)
        self.autotimer.timeout.connect(self.autosave)
        self.autotimer.start(30000)
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.poll_export)
        self.poll.start(350)
        QTimer.singleShot(150, self.recover)

    def tr_text(self, pl, en):
        return self.catalog[self.project.language].get(pl, pl if self.project.language == 'pl' else en)

    def text(self, obj, pl, en):
        self.translated.append((obj, pl, en))
        obj.setText(self.tr_text(pl, en))
        return obj

    def button(self, pl, en, callback, layout):
        b = self.text(QPushButton(), pl, en)
        b.clicked.connect(callback)
        layout.addWidget(b)
        return b

    def action(self, pl, en, shortcut, callback):
        a = self.text(QAction(self), pl, en)
        a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(callback)
        self.addAction(a)
        return a

    def build(self):
        help_menu = self.menuBar().addMenu('Pomoc / Help')
        help_menu.addAction(self.action('O aplikacji i licencjach', 'About and licenses', 'F1', self.about))
        toolbar = self.addToolBar('Project')
        toolbar.setMovable(False)
        for pl, en, key, cb in [('Nowy projekt', 'New project', 'Ctrl+N', self.new_project),
                                ('Otwórz film', 'Open video', 'Ctrl+O', self.open_video),
                                ('Importuj napisy', 'Import subtitles', 'Ctrl+I', self.import_subtitles),
                                ('Dodaj logo', 'Add logo', 'Ctrl+L', self.add_logo),
                                ('Otwórz projekt', 'Open project', 'Ctrl+Shift+O', self.open_project),
                                ('Zapisz projekt', 'Save project', 'Ctrl+S', self.save_project),
                                ('Eksportuj napisy', 'Export subtitles', 'Ctrl+Shift+S', self.export_subtitles),
                                ('Eksportuj film', 'Export video', 'Ctrl+E', self.export_video)]:
            toolbar.addAction(self.action(pl, en, key, cb))
        self.action('Cofnij', 'Undo', 'Ctrl+Z', self.undo)
        self.action('Ponów', 'Redo', 'Ctrl+Y', self.redo)
        self.action('Odtwarzaj / pauza', 'Play / pause', 'Space', self.play)
        self.action('Poprzednia klatka', 'Previous frame', 'Left', lambda: self.step(-1))
        self.action('Następna klatka', 'Next frame', 'Right', lambda: self.step(1))
        self.action('Pełny ekran', 'Full screen', 'F11', lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 10, 16, 12)
        top = QHBoxLayout()
        brand = QLabel()
        brand.setPixmap(self.windowIcon().pixmap(36,36))
        top.addWidget(brand)
        title = QLabel('SUBTITLE <span style="color:#9b9eff">STUDIO</span>')
        title.setStyleSheet('font-size:22px; font-weight:700; padding:8px 0')
        top.addWidget(title)
        top.addStretch()
        self.lang = QComboBox()
        self.lang.addItems(['Polski', 'English'])
        self.lang.currentIndexChanged.connect(self.change_language)
        top.addWidget(self.lang)
        self.theme = QComboBox()
        self.theme.addItems(['Ciemny / Dark', 'Jasny / Light', 'System'])
        self.theme.currentIndexChanged.connect(self.change_theme)
        top.addWidget(self.theme)
        root.addLayout(top)
        upper = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.addWidget(self.text(QLabel(), 'PLIKI I WARSTWY', 'FILES & LAYERS'))
        self.layers = QListWidget()
        self.layers.currentRowChanged.connect(self.select_layer)
        ll.addWidget(self.layers)
        self.button('Widoczność', 'Toggle visibility', self.toggle_layer, ll)
        self.button('Warstwa w górę', 'Move layer up', self.layer_up, ll)
        self.button('Usuń warstwę', 'Delete layer', self.delete_layer, ll)
        self.meta = QLabel('')
        self.meta.setWordWrap(True)
        ll.addWidget(self.meta)
        upper.addWidget(left)
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        self.preview = Preview()
        self.preview.project = self.project
        self.preview.moved.connect(self.move_layer)
        cl.addWidget(self.preview, 1)
        transport = QHBoxLayout()
        self.button('◀', '◀', lambda: self.step(-1), transport)
        self.button('▶ / Ⅱ', '▶ / Ⅱ', self.play, transport)
        self.button('▶', '▶', lambda: self.step(1), transport)
        self.clock = QLabel('00:00:00.000')
        transport.addWidget(self.clock)
        transport.addStretch()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.audio.setVolume(.7)
        self.volume.setMaximumWidth(110)
        self.volume.valueChanged.connect(lambda v: self.audio.setVolume(v/100))
        transport.addWidget(QLabel('♪'))
        transport.addWidget(self.volume)
        cl.addLayout(transport)
        self.scrub = QSlider(Qt.Orientation.Horizontal)
        self.scrub.sliderMoved.connect(self.player.setPosition)
        cl.addWidget(self.scrub)
        upper.addWidget(center)
        props = QWidget()
        form = QFormLayout(props)
        form.setContentsMargins(12, 0, 0, 0)
        def row(pl, en, widget):
            label = self.text(QLabel(), pl, en)
            form.addRow(label, widget)
        self.presets = QComboBox()
        self.presets.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.presets.setMinimumContentsLength(15)
        self.preset_data = json.loads((ROOT/'assets/presets/defaults.json').read_text(encoding='utf-8'))
        self.presets.addItems([p['name'] for p in self.preset_data])
        self.presets.activated.connect(self.apply_preset)
        row('Szablon', 'Preset', self.presets)
        b = QPushButton()
        self.text(b, 'Zapisz własny preset', 'Save custom preset')
        b.clicked.connect(self.save_preset)
        form.addRow(b)
        b = QPushButton()
        self.text(b, 'Wczytaj preset JSON', 'Load JSON preset')
        b.clicked.connect(self.load_preset)
        form.addRow(b)
        self.font_combo = QComboBox()
        self.font_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.font_combo.setMinimumContentsLength(12)
        from PySide6.QtGui import QFontDatabase
        self.font_combo.addItems(QFontDatabase.families())
        row('Czcionka', 'Font', self.font_combo)
        self.size = QSpinBox(); self.size.setRange(8, 300)
        row('Rozmiar / 1080p', 'Size / 1080p', self.size)
        self.bold = QCheckBox()
        row('Pogrubienie', 'Bold', self.bold)
        self.color = ColorButton()
        self.background = ColorButton('#00000000')
        self.outline_color = ColorButton('#111111')
        self.active_color = ColorButton('#ffdc55')
        for field, widget, pl, en in [
                ('color',self.color,'Kolor napisów','Subtitle color'),
                ('outline',self.outline_color,'Kolor obrysu','Outline color'),
                ('background',self.background,'Kolor tła','Background color'),
                ('active_color',self.active_color,'Aktywne słowo','Active word')]:
            row(pl,en,widget)
            widget.clicked.connect(lambda checked=False, key=field, button=widget: self.choose_color(key,button))
        self.stroke = QSpinBox(); self.stroke.setRange(0, 15)
        row('Obrys', 'Outline', self.stroke)
        self.effect = QComboBox()
        self.effect.addItems(['static', 'fade', 'left', 'right', 'up', 'typewriter', 'words', 'highlight', 'pop'])
        self.effect.setToolTip('Aktywne słowo: czasy z „Słowa” lub równy podział segmentu. / Highlight: manual word timings or equal intervals.')
        row('Animacja', 'Animation', self.effect)
        self.anim = QSpinBox(); self.anim.setRange(1, 5000); self.anim.setSuffix(' ms')
        row('Czas animacji', 'Animation duration', self.anim)
        self.anchors = QComboBox()
        self.anchors.addItems(['↖','↑','↗','←','●','→','↙','↓','↘'])
        self.anchors.activated.connect(self.anchor)
        row('Pozycja w siatce', 'Grid position', self.anchors)
        self.x = QDoubleSpinBox(); self.x.setRange(0, 100); self.x.setSuffix('%')
        self.y = QDoubleSpinBox(); self.y.setRange(0, 100); self.y.setSuffix('%')
        row('Pozycja X', 'Position X', self.x)
        row('Pozycja Y', 'Position Y', self.y)
        self.logo_width = QDoubleSpinBox(); self.logo_width.setRange(1, 100); self.logo_width.setSuffix('%')
        row('Szerokość logo / film', 'Logo width / video', self.logo_width)
        self.logo_slider = QSlider(Qt.Orientation.Horizontal); self.logo_slider.setRange(1,100)
        self.logo_slider.valueChanged.connect(self.logo_width.setValue)
        self.logo_width.valueChanged.connect(lambda v: self.logo_slider.setValue(round(v)))
        form.addRow(self.logo_slider)
        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(0, 100)
        self.opacity_label = QLabel('100%')
        opacity_box = QWidget(); ol = QHBoxLayout(opacity_box); ol.setContentsMargins(0,0,0,0)
        ol.addWidget(self.opacity); ol.addWidget(self.opacity_label)
        row('Krycie logo', 'Logo opacity', opacity_box)
        self.logo_start = QSpinBox(); self.logo_start.setRange(0, 2147483647)
        self.logo_end = QSpinBox(); self.logo_end.setRange(0, 2147483647)
        row('Logo początek ms', 'Logo start ms', self.logo_start)
        row('Logo koniec ms', 'Logo end ms', self.logo_end)
        for widget in (self.font_combo, self.effect):
            widget.currentTextChanged.connect(self.properties_changed)
        for widget in (self.size, self.stroke, self.anim, self.x, self.y, self.logo_width, self.opacity, self.logo_start, self.logo_end):
            widget.valueChanged.connect(self.properties_changed)
        self.bold.toggled.connect(self.properties_changed)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(props); scroll.setMinimumWidth(290)
        upper.addWidget(scroll)
        upper.setSizes([190, 850, 310])
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(upper)
        lower = QWidget(); lo = QVBoxLayout(lower); lo.setContentsMargins(0,8,0,0)
        controls = QHBoxLayout()
        self.button('+ Segment', '+ Segment', self.add_segment, controls)
        self.button('Usuń', 'Delete', self.delete_segment, controls)
        self.button('Podziel', 'Split', self.split_segment, controls)
        self.button('Połącz', 'Merge', self.merge_segments, controls)
        self.button('Początek ◷', 'Start ◷', lambda: self.set_time(True), controls)
        self.button('Koniec ◷', 'End ◷', lambda: self.set_time(False), controls)
        self.button('Przesuń ms', 'Shift ms', self.shift_dialog, controls)
        self.button('Dwa punkty', 'Two anchors', self.stretch_dialog, controls)
        self.button('Słowa', 'Word timing', self.words_dialog, controls)
        self.button('Pisownia', 'Spelling', self.spelling, controls)
        self.button('Znajdź / zamień', 'Find / replace', self.replace, controls)
        self.button('QC', 'QC', self.quality_dialog, controls)
        lo.addLayout(controls)
        self.table = QTableWidget(0, 6)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self.cell_changed)
        self.table.cellDoubleClicked.connect(lambda row, col: self.player.setPosition(self.track().segments[row].start) if col in (0,1) else None)
        lo.addWidget(self.table)
        self.timeline = Timeline(); self.timeline.seek.connect(self.player.setPosition)
        lo.addWidget(self.timeline)
        vertical.addWidget(lower); vertical.setSizes([520, 330])
        root.addWidget(vertical, 1)
        self.exportbar = QWidget(); el = QHBoxLayout(self.exportbar); el.setContentsMargins(0,0,0,0)
        self.progress = QProgressBar(); el.addWidget(self.progress)
        self.eta = QLabel(); el.addWidget(self.eta)
        self.button('Anuluj eksport', 'Cancel export', self.cancel_export, el)
        self.exportbar.hide(); root.addWidget(self.exportbar)
        self.setCentralWidget(central)

    def error(self, message):
        QMessageBox.warning(self, 'Subtitle Studio', str(message))

    def about(self):
        QMessageBox.information(self,f'Subtitle Studio {VERSION}',self.tr_text(
            'Lokalny edytor napisów i logo.\nKod aplikacji: MIT. PySide6 / Qt: LGPL v3.\nQt Multimedia korzysta z bibliotek FFmpeg (LGPL v2.1+).\nZewnętrzne ffmpeg.exe i ffprobe.exe nie są dołączone.\nPełne licencje: folder licenses i THIRD_PARTY.md.\nZakres implementacji: docs/STATUS.md.',
            'Local subtitle and logo editor.\nApplication: MIT. PySide6 / Qt: LGPL v3.\nQt Multimedia uses FFmpeg libraries (LGPL v2.1+).\nExternal ffmpeg.exe and ffprobe.exe are not bundled.\nFull licenses: licenses folder and THIRD_PARTY.md.\nImplemented scope: docs/STATUS.md.'))

    def track(self):
        return self.project.tracks[min(self.active_track, len(self.project.tracks)-1)]

    def checkpoint(self):
        self.history.append(copy.deepcopy(self.project.data()))
        self.history = self.history[-60:]
        self.future.clear()
        self.dirty = True
        self.update_title()

    def update_title(self):
        self.setWindowTitle(('● ' if self.dirty else '')+'Subtitle Studio — '+(Path(self.path).stem if self.path else self.tr_text('Nowy projekt', 'New project')))

    def undo(self):
        if self.history:
            old_video = self.project.video
            self.future.append(self.project.data())
            self.project = Project.from_data(self.history.pop())
            self.dirty = True
            self.restore_view(old_video)

    def redo(self):
        if self.future:
            old_video = self.project.video
            self.history.append(self.project.data())
            self.project = Project.from_data(self.future.pop())
            self.dirty = True
            self.restore_view(old_video)

    def restore_view(self, old_video):
        self.retranslate(); self.apply_theme()
        if old_video != self.project.video:
            self.player.setSource(QUrl.fromLocalFile(self.project.video) if self.project.video else QUrl())
            if self.project.video:
                path = self.project.video
                self.pool.start(Job(lambda: probe(path), lambda info: self.restore_metadata(path,info), self.error))
            else:
                self.preview.frame = QImage(); self.meta.clear()
                self.info['duration'] = 0; self.timeline.duration = 1; self.timeline.wave = []

    def restore_metadata(self, path, info):
        if self.project.video == path:
            self.info = info; self.scrub.setRange(0,info['duration']); self.timeline.duration = info['duration']
            self.refresh()

    def refresh(self):
        self.loading = True
        self.active_track = min(self.active_track, len(self.project.tracks)-1)
        self.active_logo = min(self.active_logo, len(self.project.logos)-1)
        self.preview.project = self.project
        self.timeline.project = self.project
        self.layers.clear()
        self.layers.addItem('🎬 '+(Path(self.project.video).name if self.project.video else self.tr_text('Brak filmu', 'No video')))
        for t in self.project.tracks:
            self.layers.addItem(('● ' if t.visible else '○ ')+t.name)
        for l in self.project.logos:
            self.layers.addItem(('● ' if l.visible else '○ ')+'Logo · '+Path(l.path).name)
        self.layers.setCurrentRow(1+len(self.project.tracks)+self.active_logo if self.active_logo >= 0 else self.active_track+1)
        self.table.setHorizontalHeaderLabels([self.tr_text('Początek', 'Start'), self.tr_text('Koniec', 'End'),
            self.tr_text('Tekst', 'Text'), self.tr_text('Język', 'Language'), 'ms', self.tr_text('Kontrola jakości', 'Quality checks')])
        self.table.setRowCount(len(self.track().segments))
        checks = warnings(self.track().segments, self.info['duration'], **self.project.quality)
        for i, s in enumerate(self.track().segments):
            for j, val in enumerate([timecode(s.start), timecode(s.end), s.text, s.language, str(s.end-s.start), checks[i]]):
                item = QTableWidgetItem(val)
                if j >= 4:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 5 and val:
                    item.setForeground(QColor('#dfaa65'))
                self.table.setItem(i, j, item)
        self.lang.setCurrentIndex(0 if self.project.language == 'pl' else 1)
        self.theme.setCurrentIndex(['dark','light','system'].index(self.project.theme))
        self.loading = False
        self.show_properties()
        self.preview.update(); self.timeline.update()
        self.update_title()

    def select_layer(self, row):
        if self.loading:
            return
        self.active_logo = row-1-len(self.project.tracks) if row > len(self.project.tracks) else -1
        if 1 <= row <= len(self.project.tracks):
            self.active_track = row-1
            self.refresh()
        else:
            self.show_properties()

    def show_properties(self):
        self.loading = True
        s = self.track().style
        self.font_combo.setCurrentText(s.font); self.size.setValue(s.size); self.bold.setChecked(s.bold)
        self.color.set_color(s.color); self.background.set_color(s.background); self.stroke.setValue(s.stroke)
        self.outline_color.set_color(s.outline); self.active_color.set_color(s.active_color)
        for button in (self.color,self.background,self.outline_color,self.active_color):
            button.setEnabled(self.active_logo < 0)
        self.effect.setCurrentText(s.effect); self.anim.setValue(s.animation_ms)
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else s
        self.x.setValue(obj.x); self.y.setValue(obj.y)
        if self.active_logo >= 0:
            self.logo_width.setValue(obj.width); self.opacity.setValue(obj.opacity)
            self.logo_start.setValue(obj.start); self.logo_end.setValue(obj.end)
        for widget in (self.logo_width, self.logo_slider, self.opacity, self.logo_start, self.logo_end):
            widget.setEnabled(self.active_logo >= 0)
        self.opacity_label.setText(f'{self.opacity.value()}%')
        self.loading = False

    def properties_changed(self, *args):
        if self.loading:
            return
        self.checkpoint()
        s = self.track().style
        s.font = self.font_combo.currentText(); s.size = self.size.value(); s.bold = self.bold.isChecked()
        s.color = self.color.value(); s.background = self.background.value(); s.stroke = self.stroke.value()
        s.outline = self.outline_color.value(); s.active_color = self.active_color.value()
        s.effect = self.effect.currentText(); s.animation_ms = self.anim.value()
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else s
        obj.x = self.x.value(); obj.y = self.y.value()
        if self.active_logo >= 0:
            obj.width = self.logo_width.value(); obj.opacity = self.opacity.value()
            obj.start = self.logo_start.value(); obj.end = self.logo_end.value()
        self.opacity_label.setText(f'{self.opacity.value()}%')
        self.preview.update(); self.timeline.update()

    def choose_color(self, field, button):
        style = self.track().style
        original = getattr(style,field)
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.player.pause()
        self._color_session = True
        translator = QTranslator(self)
        if self.project.language == 'pl':
            translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if translator.load('qtbase_pl', translations) or translator.load(str(ROOT/'assets/i18n/qtbase_pl.qm')):
                QCoreApplication.installTranslator(translator)
        dialog = QColorDialog(QColor(original),self)
        dialog.setWindowTitle(self.tr_text('Wybierz kolor — podgląd na filmie', 'Choose color — live video preview'))
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel,True)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog,True)
        def preview_color(color):
            if color.isValid():
                button.set_color(color)
                setattr(style,field,button.value())
                self.preview.update()
        dialog.currentColorChanged.connect(preview_color)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            selected = dialog.currentColor()
            # Restore before checkpointing so Undo reverses the whole picker session.
            setattr(style,field,original)
            if accepted and selected.isValid() and selected != QColor(original):
                self.checkpoint()
                preview_color(selected)
            else:
                button.set_color(original)
            self.preview.update()
        finally:
            self._color_session = False
            QCoreApplication.removeTranslator(translator)
            translator.deleteLater()
            dialog.deleteLater()
            if was_playing:
                self.player.play()

    def move_layer(self, x, y):
        if not self.history or time.monotonic()-getattr(self, '_last_drag', 0) > 1:
            self.checkpoint()
        self._last_drag = time.monotonic()
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else self.track().style
        obj.x, obj.y = x, y
        self.show_properties(); self.preview.update()

    def anchor(self, index):
        self.checkpoint()
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else self.track().style
        obj.x = [15,50,85][index % 3]
        obj.y = [12,50,88][index // 3]
        self.show_properties(); self.preview.update()

    def quality_dialog(self):
        value, ok = QInputDialog.getText(self,'QC',self.tr_text('Limity: znaki/s, znaki/wiersz, min. czas ms', 'Limits: chars/s, chars/line, min. duration ms'),
            text=','.join(str(self.project.quality[k]) for k in ('cps','line','minimum')))
        if ok:
            try:
                values = [int(v.strip()) for v in value.split(',')]
                if len(values) != 3 or any(v <= 0 for v in values):
                    raise ValueError('Wymagane 3 dodatnie liczby / Three positive numbers required')
                self.checkpoint(); self.project.quality = dict(zip(('cps','line','minimum'), values)); self.refresh()
            except ValueError as e:
                self.error(e)

    def video_frame(self, frame):
        if self.player.source().isEmpty():
            return
        img = frame.toImage()
        if not img.isNull():
            self.preview.frame = img
            self.preview.ms = frame.startTime()/1000 if frame.startTime() >= 0 else self.player.position()
            self.preview.update()

    def position(self, ms):
        self.clock.setText(timecode(ms))
        if not self.scrub.isSliderDown():
            self.scrub.setValue(ms)
        self.timeline.ms = ms; self.timeline.update()

    def play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def step(self, direction):
        self.player.pause()
        self.player.setPosition(max(0, self.player.position()+round(direction*1000/self.info['fps'])))

    def open_video(self, path=None):
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, self.tr_text('Otwórz film', 'Open video'), '', 'Video (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.mpg *.mpeg *.m4v *.ts *.mts *.m2ts *.flv *.3gp);;All (*)')
        if path:
            self.statusBar().showMessage(self.tr_text('Analiza filmu…', 'Analyzing video…'))
            project = self.project
            self.pool.start(Job(lambda: probe(path),
                                lambda info: self.set_video(path, info) if self.project is project else None,
                                lambda error: self.error(error) if self.project is project else None))

    def set_video(self, path, info):
        self.checkpoint()
        self.project.video = str(Path(path).resolve())
        self.info = info
        self.player.setSource(QUrl.fromLocalFile(self.project.video))
        self.player.pause()
        self.scrub.setRange(0, info['duration']); self.timeline.duration = info['duration']
        self.meta.setText(f"{info['width']} × {info['height']}\n{info['fps']:.3f} FPS · {info['codec']}\n{timecode(info['duration'])}\n"+
                          '\n'.join(f"{s['codec_type']}: {s.get('codec_name','?')}" for s in info.get('streams',[])))
        self.refresh()
        self.statusBar().showMessage(self.tr_text('Film gotowy. Tworzenie fali audio…', 'Video ready. Building waveform…'))
        self.pool.start(Job(lambda: waveform(path), lambda wave: self.set_wave(path, wave), lambda _: None))

    def set_wave(self, path, wave):
        if Path(path).resolve() == Path(self.project.video).resolve():
            self.timeline.wave = wave; self.timeline.update()
            self.statusBar().showMessage(self.tr_text('Gotowe', 'Ready'))

    def import_subtitles(self, path=None):
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, self.tr_text('Importuj napisy', 'Import subtitles'), '', 'Subtitles (*.srt *.vtt *.ass *.ssa *.sub *.mpl2 *.sbv *.txt *.ttml *.dfxp *.smi *.sami)')
        if not path:
            return
        encoding, ok = QInputDialog.getItem(self, 'Encoding', self.tr_text('Kodowanie', 'Encoding'), ['Auto', 'utf-8-sig', 'cp1250', 'cp1251', 'cp1252', 'utf-16'], 0, False)
        if not ok:
            return
        try:
            segments = read(path, None if encoding == 'Auto' else encoding, self.info['fps'])
            self.checkpoint()
            if self.track().segments:
                self.project.tracks.append(Track(name=Path(path).stem, segments=segments, source=str(Path(path).resolve())))
                self.active_track = len(self.project.tracks)-1
            else:
                self.track().segments = segments; self.track().name = Path(path).stem; self.track().source = str(Path(path).resolve())
            self.layers.setCurrentRow(self.active_track+1)
            self.refresh()
            if any(not s.timed for s in segments):
                self.error(self.tr_text('TXT nie zawiera czasów. Ustaw początek i koniec każdego segmentu przed eksportem.', 'TXT has no timing. Set each segment start and end before export.'))
            else:
                self.statusBar().showMessage(self.tr_text('Zaimportowano treść i czasy. Style źródłowe zastępuje styl ścieżki.', 'Imported text and timing. Track style replaces original formatting.'), 15000)
        except Exception as e:
            self.error(e)

    def add_logo(self, path=None):
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, 'Logo', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)')
        if path:
            try:
                image(path)
                self.checkpoint(); self.project.logos.append(Logo(path=str(Path(path).resolve())))
                self.active_logo = len(self.project.logos)-1
                self.refresh(); self.layers.setCurrentRow(1+len(self.project.tracks)+self.active_logo)
            except Exception as e:
                self.error(e)

    def toggle_layer(self):
        self.checkpoint()
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else self.track()
        obj.visible = not obj.visible; self.refresh()

    def layer_up(self):
        self.checkpoint()
        if self.active_logo > 0:
            i = self.active_logo; self.project.logos[i-1], self.project.logos[i] = self.project.logos[i], self.project.logos[i-1]
            self.active_logo -= 1
        elif self.active_logo < 0 and self.active_track > 0:
            i = self.active_track; self.project.tracks[i-1], self.project.tracks[i] = self.project.tracks[i], self.project.tracks[i-1]
            self.active_track -= 1
        self.refresh()

    def delete_layer(self):
        self.checkpoint()
        if self.active_logo >= 0:
            del self.project.logos[self.active_logo]; self.active_logo = -1
        elif len(self.project.tracks) > 1:
            del self.project.tracks[self.active_track]; self.active_track = 0
        self.refresh()

    def selected(self):
        return sorted(set(i.row() for i in self.table.selectedIndexes()))

    def cell_changed(self, row, col):
        if self.loading or col >= 4:
            return
        try:
            val = self.table.item(row, col).text()
            value = parse_time(val) if col < 2 else val
            self.checkpoint()
            s = self.track().segments[row]
            setattr(s, ['start','end','text','language'][col], value)
            if col < 2:
                s.timed = s.end > s.start >= 0
            if col in (0,1,2):
                s.words = []  # stale word alignment must never silently survive timing/text edits
            self.refresh()
        except Exception as e:
            self.error(e); self.refresh()

    def add_segment(self):
        self.checkpoint(); ms = self.player.position()
        self.track().segments.append(Segment(ms, ms+2000, self.tr_text('Nowy napis', 'New subtitle')))
        self.track().segments.sort(key=lambda s: s.start); self.refresh()

    def delete_segment(self):
        rows = self.selected()
        if rows:
            self.checkpoint()
            for row in reversed(rows):
                del self.track().segments[row]
            self.refresh()

    def split_segment(self):
        rows = self.selected()
        if not rows:
            return
        s = self.track().segments[rows[0]]
        ms = self.player.position()
        if not s.start < ms < s.end:
            return self.error(self.tr_text('Ustaw kursor wewnątrz segmentu.', 'Place playhead inside segment.'))
        self.checkpoint()
        words = s.text.split(); middle = max(1, len(words)//2)
        new = Segment(ms, s.end, ' '.join(words[middle:]), s.language)
        s.end = ms; s.text = ' '.join(words[:middle]); s.words = []
        self.track().segments.insert(rows[0]+1, new); self.refresh()

    def merge_segments(self):
        rows = self.selected()
        if len(rows) < 2:
            return
        if rows != list(range(rows[0], rows[-1]+1)):
            return self.error('Wybierz sąsiadujące segmenty / Select adjacent segments')
        self.checkpoint(); segments = self.track().segments
        merged = Segment(min(segments[r].start for r in rows), max(segments[r].end for r in rows),
                         ' '.join(segments[r].text for r in rows), segments[rows[0]].language)
        segments[rows[0]:rows[-1]+1] = [merged]; self.refresh()

    def set_time(self, start):
        rows = self.selected()
        if rows:
            self.checkpoint()
            for row in rows:
                s = self.track().segments[row]
                setattr(s, 'start' if start else 'end', self.player.position())
                s.timed = s.end > s.start >= 0; s.words = []
            self.refresh()

    def shift_dialog(self):
        ms, ok = QInputDialog.getInt(self, 'Sync', self.tr_text('Przesunięcie ms (zaznaczone lub cała ścieżka)', 'Shift ms (selection or entire track)'), 500, -3600000, 3600000)
        if ok:
            rows = self.selected()
            targets = [self.track().segments[r] for r in rows] if rows else self.track().segments
            try:
                self.checkpoint(); shift(targets, ms); self.refresh()
            except Exception as e:
                self.error(e)

    def stretch_dialog(self):
        value, ok = QInputDialog.getText(self, 'Sync', self.tr_text('Źródło A,B → wynik A,B (ms, przecinki). Zmieni odstępy.', 'Source A,B → target A,B (ms, commas). Gaps will change.'), text='0,60000,0,60000')
        if ok:
            try:
                values = [int(v.strip()) for v in value.split(',')]
                if len(values) != 4:
                    raise ValueError('Wymagane 4 liczby / Four numbers required')
                self.checkpoint(); stretch(self.track().segments, *values); self.refresh()
            except Exception as e:
                self.error(e)

    def words_dialog(self):
        rows = self.selected()
        if not rows:
            return
        s = self.track().segments[rows[0]]
        tokens = visible_text(s.text).split()
        if not tokens or s.end <= s.start:
            return
        dialog = QDialog(self); dialog.setWindowTitle(self.tr_text('Ręczne czasy słów', 'Manual word timing')); layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr_text('Początek i koniec w ms filmu. Brak automatycznego dopasowania do mowy.', 'Start/end in media ms. No automatic speech alignment.')))
        table = QTableWidget(len(tokens), 3); table.setHorizontalHeaderLabels(['Word', 'Start ms', 'End ms'])
        duration = s.end - s.start
        for i, word in enumerate(tokens):
            timing = s.words[i] if i < len(s.words) else dict(
                start=s.start + i * duration // len(tokens),
                end=s.start + (i + 1) * duration // len(tokens),
            )
            for j, val in enumerate([word, timing['start'], timing['end']]):
                item = QTableWidgetItem(str(val))
                if j == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i,j,item)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec():
            try:
                words = [dict(text=table.item(i,0).text(), start=int(table.item(i,1).text()), end=int(table.item(i,2).text())) for i in range(table.rowCount())]
                if any(not s.start <= w['start'] < w['end'] <= s.end for w in words) or any(a['end'] > b['start'] for a,b in zip(words, words[1:])):
                    raise ValueError('Czasy słów muszą rosnąć bez nakładania i mieścić się w segmencie.')
                self.checkpoint(); s.words = words; self.track().style.effect = 'highlight'; self.show_properties(); self.preview.update()
            except Exception as e:
                self.error(e)

    def spelling(self):
        project = self.project
        languages = {self.track().segments[row].language for row in (self.selected() or range(len(self.track().segments)))}
        self.statusBar().showMessage(self.tr_text('Ładowanie lokalnych słowników…', 'Loading local dictionaries…'))
        self.pool.start(Job(lambda: [self.spell.dictionary(language) for language in languages],
                            lambda _: self.spelling_loaded() if self.project is project else None,
                            lambda error: self.error(error) if self.project is project else None))

    def spelling_loaded(self):
        rows = self.selected() or list(range(len(self.track().segments)))
        try:
            for row in rows:
                s = self.track().segments[row]
                self.spell.dictionary(s.language)
                for word in set(re.findall(r'[^\W\d_]+', s.text, re.UNICODE)):
                    if self.spell.check(word, s.language):
                        continue
                    choices = self.spell.suggest(word, s.language)+[self.tr_text('Ignoruj', 'Ignore'), self.tr_text('Dodaj do słownika', 'Add to dictionary')]
                    value, ok = QInputDialog.getItem(self, self.tr_text('Pisownia', 'Spelling'), word, choices, 0, True)
                    if not ok:
                        return
                    if value == choices[-1]:
                        self.spell.add(word)
                    elif value != choices[-2]:
                        self.checkpoint(); s.text = re.sub(r'(?<!\w)'+re.escape(word)+r'(?!\w)', lambda _: value, s.text); s.words = []
            self.refresh()
        except Exception as e:
            self.error(e)

    def replace(self):
        old, ok = QInputDialog.getText(self, 'Find', self.tr_text('Szukaj', 'Find'))
        if not ok or not old:
            return
        new, ok = QInputDialog.getText(self, 'Replace', self.tr_text('Zamień na', 'Replace with'))
        if ok:
            self.checkpoint()
            for s in self.track().segments:
                if old in s.text:
                    s.text = s.text.replace(old, new); s.words = []
            self.refresh()

    def apply_preset(self, index):
        self.checkpoint(); self.track().style = Style(**self.preset_data[index]['style']); self.show_properties(); self.preview.update()

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Preset', '', 'JSON (*.json)')
        if path:
            from dataclasses import asdict
            Path(path).write_text(json.dumps(asdict(self.track().style), ensure_ascii=False, indent=2), encoding='utf-8')

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Preset', '', 'JSON (*.json)')
        if path:
            try:
                style = Style(**json.loads(Path(path).read_text(encoding='utf-8')))
                if not 8 <= style.size <= 300 or not 0 <= style.x <= 100 or not 0 <= style.y <= 100:
                    raise ValueError('Nieprawidłowy preset')
                self.checkpoint(); self.track().style = style; self.show_properties(); self.preview.update()
            except Exception as e:
                self.error(e)

    def save_project(self):
        path = self.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, self.tr_text('Zapisz projekt', 'Save project'), '', 'Subtitle Studio (*.subtitlelogo.json)')
        if not path:
            return False
        try:
            save(self.project, path); self.path = path; self.dirty = False
            self.autopath.unlink(missing_ok=True); self.refresh(); return True
        except Exception as e:
            self.error(e); return False

    def confirm_unsaved(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, 'Subtitle Studio', self.tr_text('Zapisać zmiany w projekcie?', 'Save project changes?'),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return self.save_project() if answer == QMessageBox.StandardButton.Save else answer == QMessageBox.StandardButton.Discard

    def new_project(self):
        if self.export_process:
            self.error(self.tr_text('Najpierw zakończ lub anuluj eksport.', 'Finish or cancel the export first.'))
            return
        if not self.confirm_unsaved():
            return
        try:
            self.autopath.unlink(missing_ok=True)
        except OSError as error:
            self.error(error)
            return

        self.project = Project(language=self.project.language, theme=self.project.theme)
        self.path = None
        self.dirty = False
        self.history.clear()
        self.future.clear()
        self.active_track = 0
        self.active_logo = -1
        self._last_drag = 0
        self.player.stop()
        self.player.setSource(QUrl())
        self.info = dict(width=1920, height=1080, duration=0, fps=25)
        self.meta.clear()
        self.preview.frame = QImage()
        self.preview.ms = 0
        self.preview.output_size = None
        self.preview.rect = QRectF()
        self.timeline.wave = []
        self.timeline.duration = 1
        self.scrub.setRange(0, 0)
        self.position(0)
        self.presets.setCurrentIndex(0)
        self.statusBar().clearMessage()
        self.refresh()

    def open_project(self, path=None):
        if not self.confirm_unsaved():
            return
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, 'Project', '', 'Subtitle Studio (*.json)')
        if not path:
            return
        try:
            project = load(path)
            for obj, key in [(project,'video')]+[(l,'path') for l in project.logos]:
                original = getattr(obj,key)
                if original and not Path(original).is_file():
                    found, _ = QFileDialog.getOpenFileName(self, self.tr_text('Wskaż brakujący plik: ', 'Locate missing file: ')+Path(original).name)
                    if not found:
                        return
                    setattr(obj, key, found)
            info = probe(project.video) if project.video else self.info
            self.project = project; self.path = path; self.history.clear(); self.future.clear(); self.active_track = 0; self.active_logo = -1
            if project.video:
                self.set_video(project.video, info)
            self.history.clear(); self.dirty = False; self.refresh(); self.retranslate(); self.apply_theme()
        except Exception as e:
            self.error(e)

    def autosave(self):
        if self.dirty and not self._color_session:
            try:
                save(self.project, self.autopath)
            except OSError:
                self.statusBar().showMessage(self.tr_text('Nie udało się zapisać kopii awaryjnej.', 'Recovery save failed.'))

    def recover(self):
        if self.autopath.exists():
            if QMessageBox.question(self, 'Recovery', self.tr_text('Odzyskać ostatnią kopię awaryjną?', 'Recover last autosave?')) == QMessageBox.StandardButton.Yes:
                self.open_project(str(self.autopath)); self.path = None; self.dirty = True

    def export_subtitles(self):
        path, _ = QFileDialog.getSaveFileName(self, self.tr_text('Eksportuj napisy (treść i czasy)', 'Export subtitles (text and timing)'), '', 'SRT (*.srt);;WebVTT (*.vtt);;ASS (*.ass)')
        if path:
            try:
                if any(t.source and Path(path).resolve() == Path(t.source).resolve() for t in self.project.tracks) or (self.project.video and Path(path).resolve() == Path(self.project.video).resolve()):
                    raise ValueError(self.tr_text('Wybierz nowy plik, aby zachować oryginał.', 'Choose a new file to preserve the original.'))
                write(self.track().segments, path)
                self.statusBar().showMessage(self.tr_text('Zapisano treść i czasy. Style i animacje aplikacji są zachowane w projekcie i wypalanym filmie.', 'Saved text and timing. App styles and animations are kept in project and rendered video.'),15000)
            except Exception as e:
                self.error(e)

    def export_video(self):
        if self.export_process is not None:
            return self.error(self.tr_text('Eksport już trwa.', 'Export is already running.'))
        if not self.project.video:
            return self.error(self.tr_text('Najpierw otwórz film.', 'Open a video first.'))
        dialog = QDialog(self); dialog.setWindowTitle(self.tr_text('Eksportuj film', 'Export video')); form = QFormLayout(dialog)
        profile = QComboBox(); profile.addItems(['MP4 · H.264 / AAC', 'MP4 · H.265 / AAC', 'WebM · VP9 / Opus', 'MKV · H.264 / AAC'])
        size = QComboBox(); size.addItems(['Source', '1920 × 1080', '3840 × 2160', '1080 × 1920', '1080 × 1080'])
        fps = QDoubleSpinBox(); fps.setRange(1,120); fps.setDecimals(3); fps.setValue(min(120,self.info['fps']))
        crf = QSpinBox(); crf.setRange(0,51); crf.setValue(20)
        test = QCheckBox(self.tr_text('Tylko pierwsze 10 sekund', 'First 10 seconds only'))
        form.addRow(self.tr_text('Profil', 'Profile'), profile); form.addRow(self.tr_text('Rozmiar (dopasuj + pasy)', 'Size (fit + bars)'), size)
        form.addRow('FPS',fps); form.addRow('CRF',crf); form.addRow(test)
        notice = QLabel(self.tr_text('Napisy i logo zostaną wypalone. Wideo będzie ponownie kodowane.\nBez ręcznych czasów podświetlenie dzieli czas segmentu równo między słowa. Zmiana FPS konwertuje VFR na CFR.',
                                    'Subtitles and logos will be burned in. Video will be re-encoded.\nWithout manual timing, each word gets an equal share of the segment. FPS selection converts VFR to CFR.'))
        notice.setWordWrap(True); form.addRow(notice)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if not dialog.exec():
            return
        idx = profile.currentIndex(); suffix = ['mp4','mp4','webm','mkv'][idx]
        target, _ = QFileDialog.getSaveFileName(self, self.tr_text('Zapisz film', 'Save video'), '', f'Video (*.{suffix})')
        if not target:
            return
        if not Path(target).suffix:
            target += '.'+suffix
        if Path(target).suffix.lower() != '.'+suffix:
            return self.error(self.tr_text('Rozszerzenie pliku musi odpowiadać profilowi.', 'File extension must match profile.'))
        dimensions = [(self.info['width'],self.info['height']), (1920,1080),(3840,2160),(1080,1920),(1080,1080)][size.currentIndex()]
        opts = dict(width=dimensions[0], height=dimensions[1], fps=fps.value(), crf=crf.value(), codec=['libx264','libx265','libvpx-vp9','libx264'][idx])
        if test.isChecked():
            opts['seconds'] = 10
        self.start_export(target, opts)

    def start_export(self, target, opts):
        self.export_temp = tempfile.TemporaryDirectory(prefix='subtitle-job-')
        folder = Path(self.export_temp.name)
        save(self.project, folder/'project.json')
        (folder/'options.json').write_text(json.dumps(opts))
        self.export_status = folder/'status.json'; self.export_cancel = folder/'cancel'
        self.preview.output_size = (opts['width'], opts['height']); self.preview.update()
        self.export_process = QProcess(self)
        self.export_process.finished.connect(self.finish_export)
        self.export_process.errorOccurred.connect(self.export_error)
        args = ['--render', str(folder/'project.json'), target, str(folder/'options.json'), str(self.export_cancel), str(self.export_status)]
        if getattr(sys,'frozen',False):
            self.export_process.start(sys.executable, args)
        else:
            self.export_process.start(sys.executable, [str(ROOT/'main.py')]+args)
        self.progress.setValue(0); self.exportbar.show()
        self.statusBar().showMessage(self.tr_text('Renderowanie w osobnym procesie…', 'Rendering in a separate process…'))

    def export_error(self, error):
        if self.export_process and error == QProcess.ProcessError.FailedToStart:
            self.finish_export(1,QProcess.ExitStatus.CrashExit)

    def poll_export(self):
        if self.export_process and self.export_status.exists():
            try:
                status = json.loads(self.export_status.read_text(encoding='utf-8'))
                self.progress.setValue(status.get('percent', self.progress.value()))
                self.eta.setText(f"ETA {status.get('eta', 0)} s")
            except (OSError, ValueError):
                pass

    def cancel_export(self):
        if self.export_process:
            self.export_cancel.touch()
            self.statusBar().showMessage(self.tr_text('Anulowanie po bieżącej klatce…', 'Cancelling after current frame…'))

    def finish_export(self, code, status):
        try:
            result = json.loads(self.export_status.read_text(encoding='utf-8')) if self.export_status.exists() else {}
        except (OSError,ValueError):
            result = {}
        self.exportbar.hide()
        process = self.export_process; self.export_process = None
        if code or not result.get('done'):
            self.error(result.get('error', self.tr_text('Nie udało się uruchomić renderowania.', 'Renderer failed to start.')))
        else:
            self.statusBar().showMessage(self.tr_text('Film wyeksportowany i sprawdzony przez ffprobe.', 'Video exported and verified with ffprobe.'),20000)
        process.deleteLater()
        self.export_temp.cleanup(); self.export_temp = None

    def retranslate(self):
        for obj, pl, en in self.translated:
            obj.setText(self.tr_text(pl,en))
        self.refresh()

    def change_language(self, index):
        if not self.loading:
            self.checkpoint(); self.project.language = ['pl','en'][index]; self.retranslate()

    def change_theme(self, index):
        if not self.loading:
            self.checkpoint(); self.project.theme = ['dark','light','system'][index]; self.apply_theme()

    def apply_theme(self):
        dark = self.project.theme == 'dark'
        if self.project.theme == 'system':
            from PySide6.QtWidgets import QApplication
            dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, panel, fg, border = ('#10141d','#1a2130','#e9edf5','#30394c') if dark else ('#eef1f7','#ffffff','#202638','#ced5e2')
        self.setStyleSheet(f'''QMainWindow,QWidget {{ background:{bg}; color:{fg}; font-family:Segoe UI; font-size:12px; }}
            QTableWidget,QListWidget,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QTextEdit {{ background:{panel}; border:1px solid {border}; border-radius:5px; padding:4px; selection-background-color:#6267ca; }}
            QPushButton {{ background:{panel}; border:1px solid {border}; border-radius:6px; padding:7px 10px; }}
            QPushButton:hover {{ border-color:#9599ff; background:#434779; color:white; }}
            QToolBar {{ background:{panel}; border:0; spacing:10px; padding:8px; }}
            QHeaderView::section {{ background:{panel}; padding:7px; border:0; border-bottom:1px solid {border}; }}
            QProgressBar {{ border:1px solid {border}; text-align:center; border-radius:4px; }}
            QProgressBar::chunk {{ background:#777cee; }}
            QSplitter::handle {{ background:{border}; }}
            QSlider::groove:horizontal {{ background:{border}; height:4px; }}
            QSlider::handle:horizontal {{ background:#a4a7ff; width:12px; margin:-5px 0; border-radius:6px; }}''')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile(); ext = Path(path).suffix.lower()
            if ext in ('.srt','.ass','.ssa','.vtt','.sub','.sbv','.mpl2','.txt','.ttml','.dfxp','.smi','.sami'):
                self.import_subtitles(path)
            elif ext in ('.png','.jpg','.jpeg','.bmp','.webp','.gif'):
                self.add_logo(path)
            elif ext == '.json':
                self.open_project(path)
            else:
                self.open_video(path)

    def closeEvent(self, event):
        if self.export_process:
            self.error(self.tr_text('Najpierw zakończ lub anuluj eksport.', 'Finish or cancel the export first.')); event.ignore(); return
        if not self.confirm_unsaved():
            event.ignore(); return
        self.autopath.unlink(missing_ok=True)
        self.player.stop(); event.accept()


def timecode(ms):
    sign = '-' if ms < 0 else ''
    ms = abs(round(ms)); sec, milli = divmod(ms,1000); minute, sec = divmod(sec,60); hour, minute = divmod(minute,60)
    return f'{sign}{hour:02}:{minute:02}:{sec:02}.{milli:03}'


def parse_time(text):
    if re.fullmatch(r'-?\d+', text.strip()):
        return int(text)
    match = re.fullmatch(r'(\d+):([0-5]\d):([0-5]\d)[.,](\d{1,3})', text.strip())
    if not match:
        raise ValueError('Format: HH:MM:SS.mmm lub liczba ms / or milliseconds')
    h,m,s,ms = match.groups()
    return (int(h)*3600+int(m)*60+int(s))*1000+int(ms.ljust(3,'0'))
