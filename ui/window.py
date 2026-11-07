import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import threading
from PySide6.QtCore import Qt, QUrl, QTimer, QProcess, QThreadPool, QStandardPaths, QTranslator, QCoreApplication, QRectF, QLibraryInfo, QItemSelectionModel, QEvent, Signal, QSettings
from PySide6.QtGui import QAction, QKeySequence, QImage, QColor, QIcon, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QPushButton, QLabel, QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox, QInputDialog,
    QSlider, QDialog, QDialogButtonBox, QProgressBar, QGroupBox, QScrollArea, QTextEdit, QColorDialog,
    QApplication, QAbstractSpinBox, QMenu, QToolButton)
from core.projects.model import Project, Track, Segment, Logo, Style, save, load
from core.subtitles.service import read, write, shift, stretch, warnings
from core.media.tools import probe
from core.compositor.render import image, visible_text
from core.spellcheck.service import Spellchecker
from ui.preview import Preview, Timeline
from ui.jobs import Job, waveform
from ui.colors import ColorButton
from core.version import VERSION
from core.subtitles.editing import duplicate, ripple_delete
from core.projects.safety import protect_output
from core.projects.recovery import RecoverySession

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


class Window(QMainWindow):
    interfaceChanged = Signal()

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
        self._media_request = 0
        self._wave_cancel = threading.Event()
        self.info = dict(width=1920, height=1080, duration=0, fps=25)
        self.export_process = None
        self.export_temp = None
        self.active_track = 0
        self.active_logo = -1
        self.translated = []
        self.ui_settings = QSettings('LocalTools', 'SubtitleStudioInterface')
        self.store = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.store.mkdir(parents=True, exist_ok=True)
        self.recovery = RecoverySession(self.store, 'editor', 'recovery.autosave.json')
        self.autopath = self.recovery.path
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
        QApplication.instance().installEventFilter(self)
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
        a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        a.triggered.connect(callback)
        self.addAction(a)
        return a

    def menu_button(self, pl, en, entries, layout):
        button = self.text(QPushButton(), pl, en)
        menu = QMenu(button)
        for label, english, callback in entries:
            action = self.text(QAction(menu), label, english)
            action.triggered.connect(callback)
            menu.addAction(action)
        button.setMenu(menu)
        layout.addWidget(button)
        return button

    def build(self):
        help_menu = self.menuBar().addMenu('Pomoc')
        self.translated.append((help_menu.menuAction(), 'Pomoc', 'Help'))
        self.help_action = self.action('Instrukcja obsługi', 'User guide', 'F1', self.show_help)
        self.shortcuts_action = self.action('Skróty klawiszowe', 'Keyboard shortcuts', 'Ctrl+F1', self.show_shortcuts)
        self.about_action = self.action('O aplikacji i licencjach', 'About and licenses', 'Shift+F1', self.about)
        for action in (self.help_action, self.shortcuts_action, self.about_action):
            help_menu.addAction(action)
        toolbar = self.addToolBar('Project')
        toolbar.setMovable(False)
        more_menu = QMenu(self)
        for pl, en, key, cb in [('Nowy projekt', 'New project', 'Ctrl+N', self.new_project),
                                ('Otwórz film', 'Open video', 'Ctrl+O', self.open_video),
                                ('Importuj napisy', 'Import subtitles', 'Ctrl+I', self.import_subtitles),
                                ('Dodaj logo', 'Add logo', 'Ctrl+L', self.add_logo),
                                ('Otwórz projekt', 'Open project', 'Ctrl+Shift+O', self.open_project),
                                ('Zapisz projekt', 'Save project', 'Ctrl+S', self.save_project),
                                ('Eksportuj napisy', 'Export subtitles', 'Ctrl+Shift+S', self.export_subtitles),
                                ('Eksportuj film', 'Export video', 'Ctrl+E', self.export_video)]:
            action = self.action(pl, en, key, cb)
            if pl in ('Nowy projekt', 'Otwórz projekt', 'Eksportuj napisy'):
                more_menu.addAction(action)
            else:
                toolbar.addAction(action)
                if pl == 'Eksportuj film':
                    self.export_action = action
                    toolbar.widgetForAction(action).setObjectName('primary')
        self.action('Cofnij', 'Undo', 'Ctrl+Z', self.undo)
        self.action('Ponów', 'Redo', 'Ctrl+Y', self.redo)
        self.action('Odtwarzaj / pauza', 'Play / pause', 'Space', lambda: self.navigate(self.play))
        self.action('Poprzednia klatka', 'Previous frame', 'Left', lambda: self.navigate(lambda: self.step(-1)))
        self.action('Następna klatka', 'Next frame', 'Right', lambda: self.navigate(lambda: self.step(1)))
        self.action('Początek filmu', 'Video start', 'Home', lambda: self.navigate(lambda: self.player.setPosition(0)))
        self.action('Koniec filmu', 'Video end', 'End', lambda: self.navigate(lambda: self.player.setPosition(self.info['duration'])))
        self.action('Poprzednia granica', 'Previous boundary', 'Ctrl+Left', lambda: self.navigate(lambda: self.jump_boundary(-1)))
        self.action('Następna granica', 'Next boundary', 'Ctrl+Right', lambda: self.navigate(lambda: self.jump_boundary(1)))
        self.action('Duplikuj napisy', 'Duplicate subtitles', 'Ctrl+D', lambda: self.navigate(self.duplicate_segments))
        self.action('Usuń i domknij napisy', 'Ripple delete subtitles', 'Shift+Delete', lambda: self.navigate(self.ripple_segments))
        self.action('Podziel napis', 'Split subtitle', 'Ctrl+B', lambda: self.navigate(self.split_segment))
        self.action('Powiększ oś', 'Zoom timeline in', 'Ctrl+=', lambda: self.timeline.set_zoom(self.timeline.zoom*1.5))
        self.action('Pomniejsz oś', 'Zoom timeline out', 'Ctrl+-', lambda: self.timeline.set_zoom(self.timeline.zoom/1.5))
        self.action('Początek zakresu', 'Range start', 'I', lambda: self.navigate(lambda: self.range_in.setValue(self.player.position())))
        self.action('Koniec zakresu', 'Range end', 'O', lambda: self.navigate(lambda: self.range_out.setValue(self.player.position())))
        more_menu.addAction(self.action('Połącz filmy', 'Join videos', 'Ctrl+J', self.join_videos))
        more_menu.addAction(self.action('Obraz + audio', 'Visual + audio', 'Ctrl+Shift+V', self.create_video))
        more = self.text(QToolButton(), 'Więcej', 'More')
        more.setMenu(more_menu)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(more)
        self.action('Pełny ekran', 'Full screen', 'F11', lambda: self.window().showNormal() if self.window().isFullScreen() else self.window().showFullScreen())
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 10, 16, 12)
        top = QHBoxLayout()
        self.brand_bar = QWidget()
        brand_layout = QHBoxLayout(self.brand_bar)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand = QLabel()
        brand.setPixmap(self.windowIcon().pixmap(36,36))
        brand_layout.addWidget(brand)
        title = QLabel('SUBTITLE <span style="color:#9b9eff">STUDIO</span>')
        title.setStyleSheet('font-size:22px; font-weight:700; padding:8px 0')
        brand_layout.addWidget(title)
        top.addWidget(self.brand_bar)
        top.addStretch()
        self.lang = QComboBox()
        self.lang.addItems(['Polski', 'English'])
        self.lang.currentIndexChanged.connect(self.change_language)
        top.addWidget(self.lang)
        self.theme = QComboBox()
        self.theme.addItems(['Ciemny / Dark', 'Jasny / Light', 'System'])
        self.theme.currentIndexChanged.connect(self.change_theme)
        top.addWidget(self.theme)
        self.interface_size = QComboBox()
        self.interface_size.addItems(['100%', '115%', '130%'])
        self.interface_size.setCurrentIndex(max(0, self.interface_size.findText(str(self.ui_settings.value('scale', '100%')))))
        self.interface_size.currentIndexChanged.connect(self.change_interface_size)
        top.addWidget(self.interface_size)
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
        self.welcome = QWidget()
        welcome_layout = QVBoxLayout(self.welcome)
        welcome_layout.addWidget(self.text(QLabel(), 'Dodaj napisy do swojego filmu', 'Add captions to your video'))
        hint = self.text(QLabel(), 'Otwórz film, rozpoznaj mowę, popraw tekst i zapisz gotowy film.',
                         'Open a video, recognize speech, review the text and export your video.')
        hint.setWordWrap(True)
        welcome_layout.addWidget(hint)
        self.button('Otwórz film', 'Open video', self.open_video, welcome_layout).setObjectName('primary')
        cl.addWidget(self.welcome)
        cl.addWidget(self.preview, 1)
        transport = QHBoxLayout()
        self.transport_buttons = []
        for symbol, pl, en, callback in [
                ('|◀', 'Poprzednia klatka', 'Previous frame', lambda: self.step(-1)),
                ('▶ / Ⅱ', 'Odtwórz / wstrzymaj', 'Play / pause', self.play),
                ('▶|', 'Następna klatka', 'Next frame', lambda: self.step(1))]:
            button = self.button(symbol, symbol, callback, transport)
            self.transport_buttons.append((button, pl, en))
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
        self.properties_form = form
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setContentsMargins(12, 0, 0, 0)
        def row(pl, en, widget):
            label = self.text(QLabel(), pl, en)
            label.setBuddy(widget)
            form.addRow(label, widget)
        self.presets = QComboBox()
        self.presets.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.presets.setMinimumContentsLength(15)
        self.preset_data = json.loads((ROOT/'assets/presets/defaults.json').read_text(encoding='utf-8'))
        self.presets.addItems([p['name'] for p in self.preset_data])
        self.presets.activated.connect(self.apply_preset)
        row('Szablon', 'Preset', self.presets)
        b = QPushButton()
        self.text(b, 'Zapisz własny styl', 'Save custom style')
        b.clicked.connect(self.save_preset)
        form.addRow(b)
        b = QPushButton()
        self.text(b, 'Wczytaj styl…', 'Load style…')
        b.clicked.connect(self.load_preset)
        form.addRow(b)
        self.font_combo = QComboBox()
        self.font_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.font_combo.setMinimumContentsLength(12)
        from PySide6.QtGui import QFontDatabase
        self.font_combo.addItems(QFontDatabase.families())
        row('Czcionka', 'Font', self.font_combo)
        self.size = QSpinBox(); self.size.setRange(8, 300)
        row('Rozmiar tekstu', 'Text size', self.size)
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
        for key,label in [('static','Bez animacji / Static'),('fade','Zanikanie / Fade'),
                          ('left','Wjazd z lewej / From left'),('right','Wjazd z prawej / From right'),
                          ('up','Wjazd z dołu / From below'),('typewriter','Maszyna do pisania / Typewriter'),
                          ('words','Kolejne słowa / Word reveal'),('highlight','Aktywne słowo / Active word'),
                          ('pop','Powiększenie / Pop')]:
            self.effect.addItem(label,key)
        self.effect.setToolTip('Aktywne i kolejne słowa: aktualne czasy ASR lub z edytora „Słowa”. '
            'Bez czasów: aktywne słowo według długości napisu, kolejne według czasu animacji. / '
            'Word effects use aligned timings when available; otherwise use equal intervals.')
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
        row('Szerokość logo (%)', 'Logo width (%)', self.logo_width)
        self.logo_slider = QSlider(Qt.Orientation.Horizontal); self.logo_slider.setRange(1,100)
        self.logo_slider.valueChanged.connect(self.logo_width.setValue)
        self.logo_width.valueChanged.connect(lambda v: self.logo_slider.setValue(round(v)))
        form.addRow(self.logo_slider)
        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(0, 100)
        self.opacity_label = QLabel('100%')
        opacity_box = QWidget(); ol = QHBoxLayout(opacity_box); ol.setContentsMargins(0,0,0,0)
        ol.addWidget(self.opacity); ol.addWidget(self.opacity_label)
        self.opacity_box = opacity_box
        row('Widoczność logo (%)', 'Logo opacity (%)', opacity_box)
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
        self.button('Dodaj napis', 'Add caption', self.add_segment, controls)
        self.button('Usuń', 'Delete', self.delete_segment, controls)
        self.button('Podziel', 'Split', self.split_segment, controls)
        self.button('Połącz', 'Merge', self.merge_segments, controls)
        self.menu_button('Synchronizacja', 'Timing', [
            ('Ustaw początek w miejscu odtwarzania', 'Set start at playhead', lambda: self.set_time(True)),
            ('Ustaw koniec w miejscu odtwarzania', 'Set end at playhead', lambda: self.set_time(False)),
            ('Przesuń napisy w czasie…', 'Shift caption timing…', self.shift_dialog),
            ('Dopasuj do dwóch punktów…', 'Align using two points…', self.stretch_dialog),
            ('Czasy poszczególnych słów…', 'Word timing…', self.words_dialog)], controls)
        self.menu_button('Sprawdzanie', 'Review', [
            ('Sprawdź pisownię', 'Check spelling', self.spelling),
            ('Znajdź i zamień…', 'Find and replace…', self.replace),
            ('Sprawdź napisy', 'Check captions', self.quality_dialog)], controls)
        controls.addStretch()
        lo.addLayout(controls)
        self.table = QTableWidget(0, 6)
        self.table.setMinimumHeight(100)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self.cell_changed)
        self.table.cellDoubleClicked.connect(lambda row, col: self.player.setPosition(self.track().segments[row].start) if col in (0,1) else None)
        lo.addWidget(self.table)
        ranges = QHBoxLayout()
        self.range_in = QSpinBox(); self.range_in.setRange(0,2147483647); self.range_in.setSuffix(' ms')
        self.range_out = QSpinBox(); self.range_out.setRange(0,2147483647); self.range_out.setSuffix(' ms')
        self.button('I · Początek', 'I · In', lambda: self.range_in.setValue(self.player.position()), ranges)
        ranges.addWidget(self.range_in)
        self.button('O · Koniec', 'O · Out', lambda: self.range_out.setValue(self.player.position()), ranges)
        ranges.addWidget(self.range_out)
        self.range_in.valueChanged.connect(self.range_changed)
        self.range_out.valueChanged.connect(self.range_changed)
        self.loop_range = self.text(QCheckBox(), 'Pętla zakresu', 'Loop range'); ranges.addWidget(self.loop_range)
        self.snap = self.text(QCheckBox(), 'Przyciągaj', 'Snap'); self.snap.setChecked(True); ranges.addWidget(self.snap)
        self.snap.toggled.connect(lambda value: setattr(self.timeline,'snapping',value))
        zoom_out = self.button('−', '−', lambda: self.timeline.set_zoom(self.timeline.zoom/1.5), ranges)
        zoom_out.setFixedWidth(34)
        self.zoom_label = QLabel('100%'); ranges.addWidget(self.zoom_label)
        zoom_in = self.button('+', '+', lambda: self.timeline.set_zoom(self.timeline.zoom*1.5), ranges)
        zoom_in.setFixedWidth(34)
        self.button('Dopasuj oś', 'Fit timeline', lambda: self.timeline.set_zoom(1), ranges)
        lo.addLayout(ranges)
        self.timeline = Timeline()
        self.timeline.seek.connect(self.player.setPosition)
        self.timeline.segmentSelected.connect(self.select_timeline_segment)
        self.timeline.segmentEdited.connect(self.edit_timeline_segment)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.timeline.zoomChanged.connect(lambda zoom: self.zoom_label.setText(f'{zoom*100:.0f}%'))
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setWidget(self.timeline)
        self.timeline_scroll.setMinimumHeight(100)
        lo.addWidget(self.timeline_scroll)
        edit_menu = self.menuBar().addMenu('Montaż')
        self.translated.append((edit_menu.menuAction(), 'Montaż', 'Edit'))
        for pl, en, key, callback in [
                ('Dodaj napis', 'Add caption', 'Insert', self.add_segment),
                ('Usuń zaznaczone napisy', 'Delete selected captions', 'Delete', self.delete_segment),
                ('Połącz zaznaczone napisy', 'Merge selected captions', 'Ctrl+Shift+B', self.merge_segments),
                ('Znajdź i zamień…', 'Find and replace…', 'Ctrl+F', self.replace),
                ('Przesuń napisy w czasie…', 'Shift caption timing…', 'Ctrl+Shift+T', self.shift_dialog),
                ('Sprawdź napisy', 'Check captions', 'Ctrl+Shift+K', self.quality_dialog)]:
            edit_menu.addAction(self.action(pl, en, key, lambda checked=False, cb=callback: self.navigate(cb)))
        edit_menu.addAction(self.action('Duplikuj napisy', 'Duplicate subtitles', '', self.duplicate_segments))
        edit_menu.addAction(self.action('Usuń i domknij napisy', 'Ripple delete subtitles', '', self.ripple_segments))
        vertical.addWidget(lower); vertical.setSizes([450, 400])
        root.addWidget(vertical, 1)
        self.exportbar = QWidget(); el = QHBoxLayout(self.exportbar); el.setContentsMargins(0,0,0,0)
        self.progress = QProgressBar(); el.addWidget(self.progress)
        self.eta = QLabel(); el.addWidget(self.eta)
        self.button('Anuluj eksport', 'Cancel export', self.cancel_export, el)
        self.exportbar.hide(); root.addWidget(self.exportbar)
        self.export_result = QWidget()
        result_layout = QHBoxLayout(self.export_result)
        self.export_result_label = QLabel()
        result_layout.addWidget(self.export_result_label, 1)
        self.button('Otwórz film', 'Open video', lambda: self.open_export(False), result_layout)
        self.button('Pokaż w folderze', 'Show in folder', lambda: self.open_export(True), result_layout)
        self.export_result.hide()
        root.addWidget(self.export_result)
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setWidget(central)
        self.setCentralWidget(self.editor_scroll)

    def error(self, message):
        from ui.appearance import show_error
        show_error(self, 'Subtitle Studio', message, self.tr_text)

    def open_export(self, folder=False):
        target = Path(self.export_target)
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))
        else:
            from ui.playback import play_video
            play_video(self, target, self.tr_text)

    def show_help(self, owner=None):
        from ui.help import HelpDialog
        owner = owner if isinstance(owner, QWidget) else self
        if isinstance(owner, HelpDialog):
            dialog = owner
        else:
            if not hasattr(owner, 'help_dialog'):
                owner.help_dialog = HelpDialog(owner)
            dialog = owner.help_dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def show_shortcuts(self, owner=None):
        self.show_help(owner).show_file('POMOC.md', 'skroty')

    def about(self):
        QMessageBox.information(self,f'Subtitle Studio {VERSION}',self.tr_text(
            'Lokalny edytor napisów i logo.\nPołączona aplikacja: GPL-3.0-or-later. PySide6 / Qt: LGPL v3.\nQt Multimedia korzysta z bibliotek FFmpeg (LGPL v2.1+).\nZewnętrzne ffmpeg.exe i ffprobe.exe nie są dołączone.\nPełne licencje: folder licenses i THIRD_PARTY.md.\nZakres implementacji: docs/STATUS.md.',
            'Local subtitle and logo editor.\nCombined application: GPL-3.0-or-later. PySide6 / Qt: LGPL v3.\nQt Multimedia uses FFmpeg libraries (LGPL v2.1+).\nExternal ffmpeg.exe and ffprobe.exe are not bundled.\nFull licenses: licenses folder and THIRD_PARTY.md.\nImplemented scope: docs/STATUS.md.'))

    def track(self):
        return self.project.tracks[min(self.active_track, len(self.project.tracks)-1)]

    def checkpoint(self):
        from core.projects.history import trim
        self.history.append(self.project.data())
        self.future.clear()
        trim(self)
        self.dirty = True
        self.update_title()

    def update_interface(self):
        self.export_action.setEnabled(bool(self.project.video) and self.export_process is None)
        for obj, pl, en in self.translated:
            obj.setText(self.tr_text(pl, en))
        for button, pl, en in self.transport_buttons:
            name = self.tr_text(pl, en)
            button.setAccessibleName(name)
            button.setToolTip(name)
        for widget, pl, en in [(self.volume, 'Głośność', 'Volume'),
                              (self.scrub, 'Pozycja odtwarzania', 'Playback position'),
                              (self.lang, 'Język interfejsu', 'Interface language'),
                              (self.theme, 'Motyw interfejsu', 'Interface theme'),
                              (self.interface_size, 'Rozmiar interfejsu', 'Interface size'),
                              (self.opacity, 'Widoczność logo', 'Logo opacity'),
                              (self.logo_slider, 'Szerokość logo', 'Logo width'),
                              (self.range_in, 'Początek zakresu w milisekundach', 'Range start in milliseconds'),
                              (self.range_out, 'Koniec zakresu w milisekundach', 'Range end in milliseconds')]:
            widget.setAccessibleName(self.tr_text(pl, en))
            widget.setToolTip(self.tr_text(pl, en))
        self.theme.blockSignals(True)
        for index, (pl, en) in enumerate([('Ciemny', 'Dark'), ('Jasny', 'Light'), ('Systemowy', 'System')]):
            self.theme.setItemText(index, self.tr_text(pl, en))
        self.theme.blockSignals(False)
        self.effect.blockSignals(True)
        for index in range(self.effect.count()):
            labels = self.effect.itemText(index).split(' / ', 1)
            if len(labels) == 2:
                self.effect.setItemData(index, labels, Qt.ItemDataRole.UserRole + 1)
            labels = self.effect.itemData(index, Qt.ItemDataRole.UserRole + 1)
            if labels:
                self.effect.setItemText(index, labels[0 if self.project.language == 'pl' else 1])
        self.effect.blockSignals(False)
        for index, (pl, en) in enumerate([
                ('Lewy górny róg', 'Top left'), ('Góra', 'Top'), ('Prawy górny róg', 'Top right'),
                ('Lewa', 'Left'), ('Środek', 'Center'), ('Prawa', 'Right'),
                ('Lewy dolny róg', 'Bottom left'), ('Dół', 'Bottom'), ('Prawy dolny róg', 'Bottom right')]):
            self.anchors.setItemText(index, self.tr_text(pl, en))
        self.presets.blockSignals(True)
        for index, preset in enumerate(self.preset_data):
            labels = preset['name'].split(' / ', 1)
            self.presets.setItemText(index, labels[0] if self.project.language == 'pl' else labels[-1])
        self.presets.blockSignals(False)
        self.table.setAccessibleName(self.tr_text('Napisy i czasy wyświetlania', 'Captions and timing'))
        self.layers.setAccessibleName(self.tr_text('Pliki i warstwy', 'Files and layers'))
        self.timeline.setAccessibleName(self.tr_text('Oś czasu napisów; czasy możesz także edytować w tabeli',
                                                       'Caption timeline; timings can also be edited in the table'))
        self.interfaceChanged.emit()

    def update_title(self):
        self.setWindowTitle(('● ' if self.dirty else '')+'Subtitle Studio — '+(Path(self.path).stem if self.path else self.tr_text('Nowy projekt', 'New project')))

    def undo(self):
        if self.history:
            old_video = self.project.video
            self.future.append(self.project.data())
            self.project = Project.from_data(self.history.pop())
            from core.projects.history import trim
            trim(self)
            self.dirty = True
            self.restore_view(old_video)

    def redo(self):
        if self.future:
            old_video = self.project.video
            self.history.append(self.project.data())
            self.project = Project.from_data(self.future.pop())
            from core.projects.history import trim
            trim(self)
            self.dirty = True
            self.restore_view(old_video)

    def restore_view(self, old_video):
        self.timeline.drag = None
        self.timeline.ghost = None
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
        self.welcome.setVisible(not self.project.video)
        self.preview.setVisible(bool(self.project.video))
        selected = self.selected()
        self.active_track = min(self.active_track, len(self.project.tracks)-1)
        self.active_logo = min(self.active_logo, len(self.project.logos)-1)
        self.preview.project = self.project
        self.timeline.project = self.project
        self.layers.clear()
        self.layers.addItem(Path(self.project.video).name if self.project.video else self.tr_text('Brak filmu', 'No video'))
        for t in self.project.tracks:
            self.layers.addItem(('● ' if t.visible else '○ ')+t.name)
        for l in self.project.logos:
            self.layers.addItem(('● ' if l.visible else '○ ')+'Logo · '+Path(l.path).name)
        self.layers.setCurrentRow(1+len(self.project.tracks)+self.active_logo if self.active_logo >= 0 else self.active_track+1)
        self.table.setHorizontalHeaderLabels([self.tr_text('Początek', 'Start'), self.tr_text('Koniec', 'End'),
            self.tr_text('Tekst', 'Text'), self.tr_text('Język', 'Language'), 'ms', self.tr_text('Kontrola jakości', 'Quality checks')])
        self.table.setRowCount(len(self.track().segments))
        signature = (tuple((s.start,s.end,s.text,s.timed) for s in self.track().segments),
                     self.info['duration'],tuple(sorted(self.project.quality.items())))
        if getattr(self,'_checks_signature',None) != signature:
            self._checks = warnings(self.track().segments,self.info['duration'],**self.project.quality)
            self._checks_signature = signature
        checks = self._checks
        for i, s in enumerate(self.track().segments):
            for j, val in enumerate([timecode(s.start), timecode(s.end), s.text, s.language, str(s.end-s.start), checks[i]]):
                item = self.table.item(i,j)
                if item is None:
                    item = QTableWidgetItem(val)
                    self.table.setItem(i,j,item)
                elif item.text() != val:
                    item.setText(val)
                if j >= 4:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 5:
                    warning_color = '#f0c06c' if self.palette().window().color().lightness() < 128 else '#845200'
                    item.setForeground(QColor(warning_color) if val else self.palette().text())
        self.lang.setCurrentIndex(0 if self.project.language == 'pl' else 1)
        self.theme.setCurrentIndex(['dark','light','system'].index(self.project.theme))
        self.range_in.setValue(self.project.range_start)
        self.range_out.setValue(self.project.range_end or self.info['duration'])
        self.timeline.setMinimumHeight(max(100,80+24*len(self.project.tracks)))
        self.table.clearSelection()
        for row in selected:
            if row < self.table.rowCount():
                self.table.selectionModel().select(self.table.model().index(row,0),QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.loading = False
        self.show_properties()
        self.preview.update(); self.timeline.update()
        self.update_title()
        self.update_interface()

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
        self.effect.setCurrentIndex(self.effect.findData(s.effect)); self.anim.setValue(s.animation_ms)
        obj = self.project.logos[self.active_logo] if self.active_logo >= 0 else s
        self.x.setValue(obj.x); self.y.setValue(obj.y)
        if self.active_logo >= 0:
            self.logo_width.setValue(obj.width); self.opacity.setValue(obj.opacity)
            self.logo_start.setValue(obj.start); self.logo_end.setValue(obj.end)
        for widget in (self.logo_width, self.logo_slider, self.opacity, self.logo_start, self.logo_end):
            widget.setEnabled(self.active_logo >= 0)
        self.opacity_label.setText(f'{self.opacity.value()}%')
        common = (self.anchors, self.x, self.y)
        logo = (self.logo_width, self.logo_slider, self.opacity_box, self.logo_start, self.logo_end)
        for row in range(self.properties_form.rowCount()):
            item = self.properties_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            widget = item.widget() if item else None
            self.properties_form.setRowVisible(row, widget in common or
                (widget in logo if self.active_logo >= 0 else widget not in logo))
            label = self.properties_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if widget and label and label.widget():
                widget.setAccessibleName(label.widget().text())
        self.loading = False

    def properties_changed(self, *args):
        if self.loading:
            return
        self.checkpoint()
        s = self.track().style
        s.font = self.font_combo.currentText(); s.size = self.size.value(); s.bold = self.bold.isChecked()
        s.color = self.color.value(); s.background = self.background.value(); s.stroke = self.stroke.value()
        s.outline = self.outline_color.value(); s.active_color = self.active_color.value()
        s.effect = self.effect.currentData(); s.animation_ms = self.anim.value()
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
        # Also update overlays while seeking a paused or low-frame-rate video.
        self.preview.ms = ms
        self.preview.update()
        if not self.scrub.isSliderDown():
            self.scrub.setValue(ms)
        self.timeline.ms = ms; self.timeline.update()
        if self.timeline.zoom > 1 and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.timeline_scroll.ensureVisible(round(self.timeline.x_at(ms)),50,60,20)
        end = self.project.range_end or self.info['duration']
        if self.loop_range.isChecked() and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            if end > self.project.range_start and ms >= end:
                self.player.setPosition(self.project.range_start)

    def play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            end = self.project.range_end or self.info['duration']
            if self.loop_range.isChecked() and end > self.project.range_start:
                if not self.project.range_start <= self.player.position() < end:
                    self.player.setPosition(self.project.range_start)
            self.player.play()

    def navigate(self, callback):
        focus = QApplication.focusWidget()
        if not isinstance(focus, (QLineEdit, QTextEdit, QAbstractSpinBox, QComboBox)):
            callback()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            focus = QApplication.focusWidget()
            if focus and (focus is self or self.isAncestorOf(focus)) and isinstance(focus,(QLineEdit,QTextEdit,QAbstractSpinBox,QComboBox)):
                keys = (Qt.Key.Key_Space,Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Home,Qt.Key.Key_End,
                        Qt.Key.Key_I,Qt.Key.Key_O,Qt.Key.Key_D,Qt.Key.Key_B,Qt.Key.Key_Delete,Qt.Key.Key_Insert)
                if event.key() in keys:
                    event.accept()
                    return True
        return super().eventFilter(watched,event)

    def range_changed(self):
        if self.loading or not self.info['duration']:
            return
        start = min(self.range_in.value(),self.info['duration']-1)
        end = min(self.info['duration'],max(1,self.range_out.value()))
        if self.sender() is self.range_in:
            end = max(start+1,end)
        else:
            start = min(start,end-1)
        self.checkpoint()
        self.project.range_start, self.project.range_end = start, end
        self.loading = True
        self.range_in.setValue(start)
        self.range_out.setValue(end)
        self.loading = False
        self.timeline.update()

    def selection_changed(self):
        if not self.loading:
            rows = self.selected()
            self.timeline.selection = (self.active_track,rows[0]) if len(rows) == 1 else None
            self.timeline.update()

    def jump_boundary(self, direction):
        points = sorted({time for track in self.project.tracks if track.visible
                         for segment in track.segments for time in (segment.start, segment.end)})
        position = self.player.position()
        if direction > 0:
            target = next((time for time in points if time > position), self.info['duration'])
        else:
            target = next((time for time in reversed(points) if time < position), 0)
        self.player.setPosition(target)

    def select_timeline_segment(self, track, row):
        self.active_track = track
        self.active_logo = -1
        self.refresh()
        self.table.selectRow(row)
        self.table.scrollToItem(self.table.item(row,2))

    def edit_timeline_segment(self, track, row, start, end):
        segment = self.project.tracks[track].segments[row]
        self.checkpoint()
        if end-start == segment.end-segment.start:
            shift([segment],start-segment.start)
        else:
            segment.start, segment.end = start, end
            segment.words = []
            segment.review=True;segment.checked=False
        segment.timed = True
        self.refresh()
        self.table.selectRow(row)

    def duplicate_segments(self):
        rows = self.selected()
        if not rows:
            return
        try:
            result, created = duplicate(self.track().segments,rows,self.info['duration'])
            self.checkpoint()
            self.track().segments = result
            self.refresh()
            self.table.clearSelection()
            for row in created:
                self.table.selectionModel().select(self.table.model().index(row,0),QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        except ValueError as error:
            self.error(error)

    def ripple_segments(self):
        rows = self.selected()
        if not rows:
            return
        try:
            result = ripple_delete(self.track().segments,rows)
            self.checkpoint()
            self.track().segments = result
            self.refresh()
        except ValueError as error:
            self.error(error)

    def join_videos(self):
        from ui.join import JoinDialog
        dialog = JoinDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def create_video(self):
        from ui.create_video import CreateVideoDialog
        dialog = CreateVideoDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def step(self, direction):
        self.player.pause()
        self.player.setPosition(max(0, self.player.position()+round(direction*1000/self.info['fps'])))

    def open_video(self, path=None):
        if not isinstance(path, str):
            path, _ = QFileDialog.getOpenFileName(self, self.tr_text('Otwórz film', 'Open video'), '', 'Video (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.mpg *.mpeg *.m4v *.ts *.mts *.m2ts *.flv *.3gp);;All (*)')
        if path:
            self._media_request += 1
            request = self._media_request
            self.statusBar().showMessage(self.tr_text('Analiza filmu…', 'Analyzing video…'))
            project = self.project
            self.pool.start(Job(lambda: probe(path),
                                lambda info: self.set_video(path, info) if self.project is project and request == self._media_request else None,
                                lambda error: self.error(error) if self.project is project and request == self._media_request else None))

    def set_video(self, path, info, preserve_range=False):
        self.timeline.drag = None
        self.timeline.ghost = None
        self.checkpoint()
        self.project.video = str(Path(path).resolve())
        self.info = info
        if not preserve_range:
            self.project.range_start = 0
            self.project.range_end = info['duration']
        self.timeline.wave = []
        self.timeline.set_zoom(1)
        self.player.setSource(QUrl.fromLocalFile(self.project.video))
        self.player.pause()
        self.scrub.setRange(0, info['duration']); self.timeline.duration = info['duration']
        self.meta.setText(f"{info['width']} × {info['height']}\n{info['fps']:.3f} FPS · {info['codec']}\n{timecode(info['duration'])}\n"+
                          '\n'.join(f"{s['codec_type']}: {s.get('codec_name','?')}" for s in info.get('streams',[])))
        self.refresh()
        self.statusBar().showMessage(self.tr_text('Film gotowy. Tworzenie fali audio…', 'Video ready. Building waveform…'))
        self.start_wave(path)

    def start_wave(self,path):
        self._wave_cancel.set();flag=threading.Event();self._wave_cancel=flag
        self.pool.start(Job(lambda:waveform(path,cancelled=flag.is_set),
            lambda wave:self.set_wave(path,wave) if not flag.is_set() else None,lambda error:None))

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
                s.review=True;s.checked=False
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
        words = s.text.split()
        if len(words) < 2:
            return self.error(self.tr_text('Napis musi mieć co najmniej dwa słowa.', 'The caption needs at least two words.'))
        aligned = len(s.words) == len(words)
        if aligned:
            middle = min(range(1,len(words)),key=lambda i: abs(s.words[i]['start']-ms))
            ms = s.words[middle]['start']
        else:
            middle, ok = QInputDialog.getInt(self, 'Podział / Split',
                self.tr_text('Liczba słów w pierwszej części', 'Words in the first part'), len(words)//2, 1, len(words)-1)
            if not ok:
                return
        self.checkpoint()
        new = Segment(ms, s.end, ' '.join(words[middle:]), s.language,
                      copy.deepcopy(s.words[middle:]) if aligned else [],review=True)
        s.end = ms; s.text = ' '.join(words[:middle]); s.words = s.words[:middle] if aligned else []
        s.review=True;s.checked=False
        self.track().segments.insert(rows[0]+1, new); self.refresh()

    def merge_segments(self):
        rows = self.selected()
        if len(rows) < 2:
            return
        if rows != list(range(rows[0], rows[-1]+1)):
            return self.error('Wybierz sąsiadujące segmenty / Select adjacent segments')
        self.checkpoint(); segments = self.track().segments
        merged = Segment(min(segments[r].start for r in rows), max(segments[r].end for r in rows),
                         ' '.join(segments[r].text for r in rows), segments[rows[0]].language,review=True,
                         original=' '.join(segments[r].original or segments[r].text for r in rows))
        segments[rows[0]:rows[-1]+1] = [merged]; self.refresh()

    def set_time(self, start):
        rows = self.selected()
        if rows:
            self.checkpoint()
            for row in rows:
                s = self.track().segments[row]
                setattr(s, 'start' if start else 'end', self.player.position())
                s.timed = s.end > s.start >= 0; s.words = []
                s.review=True;s.checked=False
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
        try:
            from ui.word_timing import WordTimingDialog
            dialog=WordTimingDialog(self,rows[0])
            if dialog.exec():dialog.apply()
            dialog.deleteLater()
        except ValueError as error:
            self.error(error)

    def spelling(self):
        if hasattr(self,'spell_delegate'):
            self.spell_delegate()
            return
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
                        s.review=True;s.checked=False
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
                    s.review=True;s.checked=False
            self.refresh()

    def apply_preset(self, index):
        self.checkpoint(); self.track().style = Style(**self.preset_data[index]['style']); self.show_properties(); self.preview.update()

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Preset', '', 'JSON (*.json)')
        if path:
            try:
                from dataclasses import asdict
                from srtstudio.project import atomic_write
                target = protect_output(self.project,path,'.json')
                atomic_write(target,json.dumps(asdict(self.track().style.validate()),ensure_ascii=False,indent=2))
            except (OSError,ValueError) as error:
                self.error(error)

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Preset', '', 'JSON (*.json)')
        if path:
            try:
                style = Style(**json.loads(Path(path).read_text(encoding='utf-8')))
                style.validate()
                self.checkpoint(); self.track().style = style; self.show_properties(); self.preview.update()
            except Exception as e:
                self.error(e)

    def save_project(self):
        if hasattr(self,'before_save'):
            self.before_save()
        path = self.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, self.tr_text('Zapisz projekt', 'Save project'), '', 'Subtitle Studio (*.subtitlelogo.json)')
        if not path:
            return False
        try:
            save(self.project, path); self.path = path; self.dirty = False
            self.autopath.unlink(missing_ok=True)
            self.recovery.discard_claims()
            if hasattr(self,'session_saved'):
                self.session_saved()
            self.refresh(); return True
        except Exception as e:
            self.error(e); return False

    def confirm_unsaved(self):
        if not self.dirty and not (hasattr(self,'session_dirty') and self.session_dirty()):
            return True
        answer = QMessageBox.question(self, 'Subtitle Studio', self.tr_text('Zapisać zmiany w projekcie?', 'Save project changes?'),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return self.save_project() if answer == QMessageBox.StandardButton.Save else answer == QMessageBox.StandardButton.Discard

    def new_project(self):
        if hasattr(self,'can_replace') and not self.can_replace():
            return False
        if self.export_process:
            self.error(self.tr_text('Najpierw zakończ lub anuluj eksport.', 'Finish or cancel the export first.'))
            return False
        if not self.confirm_unsaved():
            return False
        try:
            self.autopath.unlink(missing_ok=True)
        except OSError as error:
            self.error(error)
            return False

        self._media_request += 1
        self._wave_cancel.set()
        self.project = Project(language=self.project.language, theme=self.project.theme)
        self.recovery.discard_claims()
        self.path = None
        self.dirty = False
        self.history.clear()
        self.future.clear()
        self._history_sizes={}
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
        self.timeline.selection = None
        self.timeline.drag = None
        self.timeline.ghost = None
        self.timeline.set_zoom(1)
        self.loop_range.setChecked(False)
        self.scrub.setRange(0, 0)
        self.position(0)
        self.presets.setCurrentIndex(0)
        self.statusBar().clearMessage()
        self.refresh()
        if hasattr(self,'session_reset'):
            self.session_reset()
        return True

    def open_project(self, path=None):
        if hasattr(self,'can_replace') and not self.can_replace():
            return
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
            self._media_request += 1
            request = self._media_request
            recovering = Path(path) in self.recovery.candidates()
            def commit(info=None):
                if request != self._media_request:
                    return
                if recovering and not self.recovery.claim(path):
                    self.error('Ta kopia jest już odzyskiwana w innej sesji / Recovery is in use by another session')
                    return
                self.project = project; self.path = path; self.history.clear(); self.future.clear(); self.active_track = 0; self.active_logo = -1
                self.reset_media()
                if project.video:
                    self.set_video(project.video, info, preserve_range=True)
                self.history.clear(); self.dirty = recovering
                self._history_sizes={}
                if recovering:
                    self.path = None
                self.refresh(); self.retranslate(); self.apply_theme()
                if hasattr(self,'project_loaded'):
                    self.project_loaded()
                if recovering:
                    self.autosave()
            if project.video:
                self.pool.start(Job(lambda: probe(project.video),commit,
                    lambda error: self.error(error) if request == self._media_request else None))
            else:
                commit()
        except Exception as e:
            self.error(e)

    def autosave(self):
        if hasattr(self,'before_save'):
            self.before_save()
        if self.dirty and not self._color_session:
            try:
                save(self.project, self.autopath)
            except (OSError,ValueError,TypeError):
                self.statusBar().showMessage(self.tr_text('Nie udało się zapisać kopii awaryjnej.', 'Recovery save failed.'))

    def recover(self):
        candidates = self.recovery.candidates()
        if candidates:
            if QMessageBox.question(self, 'Recovery', self.tr_text('Odzyskać ostatnią kopię awaryjną?', 'Recover last autosave?')) == QMessageBox.StandardButton.Yes:
                self.open_project(str(candidates[0]))

    def reset_media(self):
        self._wave_cancel.set()
        self.player.stop(); self.player.setSource(QUrl())
        self.info = dict(width=1920,height=1080,duration=0,fps=25)
        self.meta.clear(); self.preview.frame = QImage(); self.preview.ms = 0
        self.preview.output_size = None; self.preview.rect = QRectF()
        self.timeline.wave = []; self.timeline.duration = 1; self.timeline.ms = 0
        self.timeline.selection = None; self.timeline.drag = None; self.timeline.ghost = None
        self.timeline.set_zoom(1); self.scrub.setRange(0,0); self.loop_range.setChecked(False)

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
        from ui.export_dialog import ExportDialog
        dialog = ExportDialog(self)
        profile, size, fps, crf = dialog.profile, dialog.size, dialog.fps, dialog.crf
        test, selected_range = dialog.test, dialog.selected_range
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
        if selected_range.isChecked():
            start = self.project.range_start
            end = self.project.range_end or self.info['duration']
            if not 0 <= start < end <= self.info['duration']:
                return self.error(self.tr_text('Ustaw poprawny zakres I–O w granicach filmu.', 'Set a valid In–Out range within the video.'))
            opts['start'] = start/1000
            opts['seconds'] = min(opts.get('seconds', (end-start)/1000), (end-start)/1000)
        self.start_export(target, opts)

    def start_export(self, target, opts):
        self.export_target = str(Path(target).resolve())
        self.export_result.hide()
        self.export_action.setEnabled(False)
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
        self.statusBar().showMessage(self.tr_text('Zapisywanie filmu… Możesz dalej przeglądać napisy.', 'Exporting video… You can keep reviewing captions.'))

    def export_error(self, error):
        if self.export_process and error == QProcess.ProcessError.FailedToStart:
            self.finish_export(1,QProcess.ExitStatus.CrashExit)

    def poll_export(self):
        if self.export_process and self.export_status.exists():
            try:
                status = json.loads(self.export_status.read_text(encoding='utf-8'))
                self.progress.setValue(status.get('percent', self.progress.value()))
                seconds = max(0, round(status.get('eta', 0)))
                self.eta.setText(self.tr_text(f'Pozostało około {seconds} s', f'About {seconds} s remaining'))
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
        self.export_action.setEnabled(bool(self.project.video))
        if self.export_cancel.exists() and not result.get('done'):
            self.statusBar().showMessage(self.tr_text('Eksport anulowany. Możesz uruchomić go ponownie.', 'Export cancelled. You can start it again.'))
        elif code or not result.get('done'):
            box = QMessageBox(self)
            box.setWindowTitle(self.tr_text('Nie udało się zapisać filmu', 'Video export failed'))
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(self.tr_text('Sprawdź wolne miejsce i dostęp do folderu docelowego. Następnie spróbuj ponownie.',
                                    'Check free disk space and access to the destination folder, then try again.'))
            box.setDetailedText(str(result.get('error', 'Renderer failed to start.')))
            retry = box.addButton(self.tr_text('Spróbuj ponownie…', 'Try again…'), QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Close)
            box.finished.connect(lambda: QTimer.singleShot(0, self.export_video) if box.clickedButton() == retry else None)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            box.open()
        else:
            self.export_result_label.setText(self.tr_text('Film zapisany: ', 'Video saved: ') + Path(self.export_target).name)
            self.export_result.show()
            self.statusBar().showMessage(self.tr_text('Film zapisany.', 'Video saved.'),20000)
        process.deleteLater()
        self.export_temp.cleanup(); self.export_temp = None
        if code == 0 and result.get('done'):
            from ui.playback import offer_playback
            offer_playback(self, self.export_target, self.tr_text)

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

    def interface_font_size(self):
        return [14, 16, 18][self.interface_size.currentIndex()]

    def change_interface_size(self, index):
        self.ui_settings.setValue('scale', self.interface_size.currentText())
        self.apply_theme()

    def apply_theme(self):
        from ui.appearance import apply_appearance
        apply_appearance(self, self.project.theme, self.interface_font_size())
        warning = '#f0c06c' if self.palette().window().color().lightness() < 128 else '#845200'
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 5)
            if item:
                item.setForeground(QColor(warning) if item.text() else self.palette().text())
        self.interfaceChanged.emit()

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
        self._wave_cancel.set();self._media_request+=1
        self.autopath.unlink(missing_ok=True)
        self.recovery.close()
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
