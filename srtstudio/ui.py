from __future__ import annotations

import copy
import json
import locale
import multiprocessing as mp
import queue
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings, Qt, QTimer, QUrl, QTranslator, QLibraryInfo
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QKeySequence, QPalette, QTextCursor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QSlider, QSplitter, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .engine import MODELS, model_ready
from .i18n import tr
from .jobs import Job
from .managers import ModelManager, settings_dialog
from .paths import data_dir, resource_dir
from .project import Project, Segment, atomic_write, export, issues, parse_time, split_segment, timestamp
from .spelling import add_word, spell_loop, user_words, word_spans, canonical
from .dictionaries import PACKS, installed, resolve
from .widgets import SpellEdit
from .branding import app_icon
from core.projects.recovery import RecoverySession


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_root = data_dir()
        self.recovery = RecoverySession(self.data_root, 'transcript', 'subtitle-studio-recovery.json')
        self.settings = QSettings("Szept", "Szept")
        default = "pl" if QLocale.system().language() == QLocale.Language.Polish else "en"
        self.ui_language = self.settings.value("language", default)
        self.project = Project()
        self.project_path = None
        self.dirty = False
        self.history = [self.project.dumps()]
        self.history_index = 0
        self.rendering = False
        self.audio_metadata = None
        self.pending_source = None
        self.active_kind = None
        self.stop_at = None
        self.spell_cache = {}
        self.suggestion_cache = {}
        self.custom_words = {}
        self.ignored, self.ignored_once = set(), set()
        self.spell_generation = 0
        self.spell_pending = False
        self.spell_requests = {}
        self.spell_errors = {}
        self.spell_failed = False
        self.suggestion_pending = None
        self.suggestion_menu = None
        self.job = Job(self)
        self.job.event.connect(self.job_event)
        self.job.finished.connect(self.job_finished)
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(.85)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(self.player_position)
        self.player.errorOccurred.connect(lambda *args: self.statusBar().showMessage(self.t("error") + ": " + self.player.errorString()))
        self.spell_timer = QTimer(self)
        self.spell_timer.setSingleShot(True)
        self.spell_timer.setInterval(650)
        self.spell_timer.timeout.connect(self.check_spelling)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self.poll_spell)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(3000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self.show_elapsed)
        self.build_ui()
        self.apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(self.apply_theme)
        self.resize(1240, 850)
        self.setMinimumSize(850, 620)
        self.setAcceptDrops(True)
        self.setWindowIcon(app_icon())
        self.restart_spelling()
        self.autosave_timer.start()
        QTimer.singleShot(200, self.recover)

    def t(self, key):
        return tr(self.ui_language, key)

    def button(self, key, callback, primary=False):
        b = QPushButton(self.t(key))
        b.clicked.connect(callback)
        if primary:
            b.setObjectName("primary")
        return b

    def build_ui(self):
        selection = {
            "recording_language": self.language.currentData() if hasattr(self, "language") else self.settings.value("recording_language", "auto"),
            "selected_model": self.model.currentData() if hasattr(self, "model") else self.settings.value("selected_model", "small"),
            "device": self.device.currentData() if hasattr(self, "device") else self.settings.value("device", "cpu"),
            "spell": self.spell.currentData() if hasattr(self, "spell") else self.settings.value("spell", "auto"),
        }
        self.rendering = True
        if hasattr(self, "full_edit"):
            for editor in (self.full_edit, self.segment_edit):
                editor.blockSignals(True)
                editor.highlighter.setDocument(None)
            self.table.blockSignals(True)
        for action in getattr(self, "shortcut_actions", []):
            action.setEnabled(False)
            action.deleteLater()
        self.shortcut_actions = []
        self.setWindowTitle(self.t("app"))
        if hasattr(self, "translator"):
            QApplication.instance().removeTranslator(self.translator)
        self.translator = QTranslator(self)
        if self.translator.load("qtbase_" + self.ui_language, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            QApplication.instance().installTranslator(self.translator)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)
        top = QHBoxLayout()
        brand = QLabel("szept")
        brand.setObjectName("brand")
        top.addWidget(brand)
        badge = QLabel(self.t("local"))
        badge.setObjectName("badge")
        top.addWidget(badge)
        top.addStretch()
        top.addWidget(self.button("models", self.open_manager))
        self.settings_button = self.button("settings", lambda: settings_dialog(self))
        top.addWidget(self.settings_button)
        layout.addLayout(top)
        subtitle = QLabel(self.t("tagline"))
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        files = QHBoxLayout()
        self.open_button = self.button("open", self.choose_audio)
        files.addWidget(self.open_button)
        files.addWidget(self.button("project", self.open_project))
        files.addWidget(self.button("save_project", self.save_project))
        files.addStretch()
        self.txt_times = QCheckBox(self.t("txt_times"))
        files.addWidget(self.txt_times)
        self.export_button = self.button("export", self.export_file, True)
        files.addWidget(self.export_button)
        layout.addLayout(files)
        self.source_label = QLabel(self.t("empty_hint"))
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("source")
        layout.addWidget(self.source_label)
        controls = QHBoxLayout()
        self.language = QComboBox()
        self.language.addItem(self.t("auto"), None)
        from faster_whisper.tokenizer import _LANGUAGE_CODES
        for code in _LANGUAGE_CODES:
            if code == "yue":
                continue  # enabled only for the large-v3 catalog model below
            self.language.addItem(self.language_name(code), code)
        for key, combo in (("language", self.language),):
            col = QVBoxLayout()
            col.addWidget(QLabel(self.t(key)))
            col.addWidget(combo)
            controls.addLayout(col, 2)
        self.model = QComboBox()
        self.refresh_models()
        self.model.currentIndexChanged.connect(self.model_changed)
        col = QVBoxLayout()
        col.addWidget(QLabel(self.t("model")))
        col.addWidget(self.model)
        controls.addLayout(col, 2)
        self.device = QComboBox()
        self.device.addItem("CPU · int8", "cpu")
        self.device.addItem("NVIDIA CUDA · int8 / float16", "cuda")
        col = QVBoxLayout()
        col.addWidget(QLabel(self.t("device")))
        col.addWidget(self.device)
        controls.addLayout(col, 2)
        self.start_button = self.button("start", self.start_asr, True)
        self.cancel_button = self.button("cancel", self.cancel_job)
        self.cancel_button.setEnabled(self.job.active)
        controls.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignBottom)
        controls.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(controls)
        status = QHBoxLayout()
        self.stage = QLabel(self.t("ready"))
        self.stage.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.elapsed = QLabel("")
        status.addWidget(self.stage)
        status.addWidget(self.progress, 1)
        status.addWidget(self.elapsed)
        layout.addLayout(status)
        player = QHBoxLayout()
        player.addWidget(self.button("play", self.toggle_play))
        player.addWidget(self.button("listen", self.listen_segment))
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self.seek_to)
        player.addWidget(self.seek, 1)
        self.clock = QLabel("00:00:00 / 00:00:00")
        player.addWidget(self.clock)
        self.speed = QComboBox()
        for rate in (.5, .75, 1, 1.25, 1.5, 2):
            self.speed.addItem(f"{rate:g}×", rate)
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(lambda: self.player.setPlaybackRate(self.speed.currentData()))
        player.addWidget(self.speed)
        layout.addLayout(player)
        editbar = QHBoxLayout()
        self.undo_button = self.button("undo", self.undo)
        self.redo_button = self.button("redo", self.redo)
        editbar.addWidget(self.undo_button)
        editbar.addWidget(self.redo_button)
        editbar.addWidget(self.button("split", self.split))
        editbar.addWidget(self.button("merge", self.merge))
        editbar.addStretch()
        editbar.addWidget(QLabel(self.t("spell")))
        self.spell = QComboBox()
        self.refresh_spell_languages()
        self.spell.currentIndexChanged.connect(lambda: self.schedule_spell())
        self.spell.setCurrentIndex(max(0, self.spell.findData(selection["spell"])))
        editbar.addWidget(self.spell)
        editbar.addWidget(self.button("spell_segment", self.set_segment_language))
        layout.addLayout(editbar)
        self.tabs = QTabWidget()
        subtitles = QWidget()
        sublayout = QVBoxLayout(subtitles)
        sublayout.setContentsMargins(0, 6, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([self.t("number"), self.t("begin"), self.t("end"), self.t("text"), self.t("warnings")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(4, 250)
        self.table.currentCellChanged.connect(self.select_segment)
        self.table.itemChanged.connect(self.table_edited)
        self.table.cellDoubleClicked.connect(lambda row, col: self.segment_edit.setFocus() if col == 3 else None)
        splitter.addWidget(self.table)
        self.segment_edit = SpellEdit(self, segment=True)
        self.segment_edit.textChanged.connect(self.segment_edited)
        self.segment_edit.setPlaceholderText(self.t("text"))
        splitter.addWidget(self.segment_edit)
        splitter.setSizes([250, 100])
        sublayout.addWidget(splitter)
        self.tabs.addTab(subtitles, self.t("segments"))
        self.full_edit = SpellEdit(self)
        self.full_edit.textChanged.connect(self.full_edited)
        self.tabs.addTab(self.full_edit, self.t("text"))
        layout.addWidget(self.tabs, 1)
        self.spell_status = QLabel("")
        self.spell_status.setWordWrap(True)
        self.spell_status.setObjectName("muted")
        spelling_bar = QHBoxLayout()
        spelling_bar.addWidget(self.spell_status, 1)
        spelling_bar.addWidget(self.button("spell_retry", self.retry_spelling))
        spelling_bar.addWidget(self.button("dictionaries_tab", self.open_dictionary_manager))
        layout.addLayout(spelling_bar)
        search = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(self.t("find"))
        self.find_input.returnPressed.connect(self.find_next)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText(self.t("replace"))
        search.addWidget(self.find_input, 1)
        search.addWidget(self.button("next", self.find_next))
        search.addWidget(self.replace_input, 1)
        search.addWidget(self.button("replace_all", self.replace_all))
        layout.addLayout(search)
        self.setCentralWidget(root)
        self.model.setCurrentIndex(max(0, self.model.findData(selection["selected_model"])))
        self.model_changed()
        self.language.setCurrentIndex(max(0, self.language.findData(selection["recording_language"])))
        self.device.setCurrentIndex(max(0, self.device.findData(selection["device"])))
        self.menuBar().clear()
        menu = self.menuBar().addMenu(self.t("app"))
        for key, shortcut, callback in [("open", "Ctrl+O", self.choose_audio), ("save_project", "Ctrl+S", self.save_project),
                                         ("export", "Ctrl+Shift+S", self.export_file), ("undo", "Ctrl+Z", self.undo),
                                         ("redo", "Ctrl+Y", self.redo), ("find", "Ctrl+F", lambda: self.find_input.setFocus()),
                                         ("listen", "Ctrl+Space", self.listen_segment)]:
            action = QAction(self.t(key), self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(callback)
            menu.addAction(action)
            self.addAction(action)
            self.shortcut_actions.append(action)
        documentation_root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else resource_dir()
        menu.addAction(self.t("readme"), lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(documentation_root / "docs" / "SZEPT.md"))))
        self.rendering = False
        self.set_busy(self.job.active)
        self.seek.setRange(0, round(self.project.duration * 1000))
        self.player_position(self.player.position())
        if self.project.source:
            self.source_label.setText(Path(self.project.source).name + " · " + timestamp(self.project.duration) + " · " + self.project.source)

    def apply_theme(self):
        theme = self.settings.value("theme", "system")
        dark = theme == "dark" or (theme == "system" and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        bg, panel, text, muted, border = ("#111820", "#1c2632", "#e6edf5", "#9babbc", "#344151") if dark else ("#f3f6fa", "#ffffff", "#1b2b3e", "#5a6b7d", "#d3dce6")
        palette = QPalette()
        for role, color in [(QPalette.ColorRole.Window, bg), (QPalette.ColorRole.Base, panel), (QPalette.ColorRole.AlternateBase, bg),
                            (QPalette.ColorRole.WindowText, text), (QPalette.ColorRole.Text, text),
                            (QPalette.ColorRole.Button, panel), (QPalette.ColorRole.ButtonText, text),
                            (QPalette.ColorRole.Highlight, "#216e60"), (QPalette.ColorRole.HighlightedText, "#ffffff")]:
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QMainWindow, QDialog {{ background: {bg}; color: {text}; }}
            QWidget {{ font-family: 'Segoe UI'; font-size: 12px; color: {text}; }}
            QMenuBar, QMenu, QTabWidget::pane {{ background: {bg}; color: {text}; }}
            QTabBar::tab {{ background: {panel}; }}
            QLabel#brand {{ font-size: 32px; font-weight: 700; letter-spacing: -1px; }}
            QLabel#badge {{ color: #269b84; font-size: 10px; font-weight: 700; padding-left: 12px; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#source {{ padding: 12px; background: {panel}; border: 1px solid {border}; border-radius: 8px; }}
            QPushButton {{ background: {panel}; border: 1px solid {border}; padding: 8px 12px; border-radius: 6px; color: {text}; }}
            QPushButton:hover {{ border-color: #269b84; }}
            QPushButton:disabled {{ color: {muted}; }}
            QPushButton#primary {{ background: #216e60; color: white; border: 1px solid #216e60; font-weight: 600; }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ padding: 6px; border: 1px solid {border}; border-radius: 5px; background: {panel}; color: {text}; }}
            QPlainTextEdit, QTableWidget {{ background: {panel}; color: {text}; border: 1px solid {border}; border-radius: 5px; selection-background-color: #216e60; }}
            QPlainTextEdit {{ font-size: 15px; padding: 10px; }}
            QHeaderView::section {{ background: {bg}; color: {muted}; padding: 7px; border: 0; }}
            QTabBar::tab {{ padding: 8px 18px; }}
            QTabBar::tab:selected {{ color: #269b84; font-weight: 600; }}
            QProgressBar {{ background: {border}; border: 0; border-radius: 4px; }}
            QProgressBar::chunk {{ background: #269b84; border-radius: 4px; }}
        """)

    def language_name(self, code):
        names = {"pl": ("Polski", "Polish"), "en": ("Angielski", "English"), "yue": ("Kantoński", "Cantonese"),
                 "de": ("Niemiecki", "German"), "fr": ("Francuski", "French"), "es": ("Hiszpański", "Spanish"),
                 "it": ("Włoski", "Italian"), "pt": ("Portugalski", "Portuguese"), "uk": ("Ukraiński", "Ukrainian"),
                 "ru": ("Rosyjski", "Russian"), "cs": ("Czeski", "Czech"), "sk": ("Słowacki", "Slovak"),
                 "nl": ("Niderlandzki", "Dutch"), "sv": ("Szwedzki", "Swedish"), "da": ("Duński", "Danish"),
                 "nb": ("Norweski bokmål", "Norwegian Bokmål"), "hu": ("Węgierski", "Hungarian"),
                 "ro": ("Rumuński", "Romanian"), "tr": ("Turecki", "Turkish")}
        base = code.split("_")[0]
        if base in names:
            return names[base][self.ui_language == "en"] + f" ({code})"
        q = QLocale(code)
        return (q.nativeLanguageName() or code) + f" ({code})"

    def dictionary_name(self, code):
        name = self.language_name(code)
        regions = {"en": ("USA", "US"), "en_GB": ("Wielka Brytania", "UK"),
                   "de": ("Niemcy", "Germany"), "de_AT": ("Austria", "Austria"),
                   "de_CH": ("Szwajcaria", "Switzerland"), "pt_PT": ("Portugalia", "Portugal"),
                   "pt_BR": ("Brazylia", "Brazil")}
        if code in regions:
            name += " · " + regions[code][self.ui_language == "en"]
        return name

    def model_root(self):
        p = Path(self.settings.value("models", str(data_dir() / "models")))
        p.mkdir(parents=True, exist_ok=True)
        return p

    def refresh_models(self):
        if not hasattr(self, "model"):
            return
        current = self.model.currentData() or "small"
        self.model.blockSignals(True)
        self.model.clear()
        for name in MODELS:
            self.model.addItem(name + (" ✓" if model_ready(self.model_root() / name) else " ↓"), name)
        external = self.settings.value("external_model", "")
        if external:
            self.model.addItem(self.t("external") + ": " + Path(external).name, external)
        self.model.setCurrentIndex(max(0, self.model.findData(current)))
        self.model.blockSignals(False)

    def model_changed(self):
        from faster_whisper.tokenizer import _LANGUAGE_CODES
        current, selected = self.language.currentData(), self.model.currentData()
        if selected in MODELS:
            codes = [c for c in _LANGUAGE_CODES if c != "yue" or selected == "large-v3"]
        else:
            try:
                tokenizer = json.loads((Path(selected) / "tokenizer.json").read_text(encoding="utf-8"))
                tokens = {t["content"] for t in tokenizer.get("added_tokens", [])}
                vocab = tokenizer.get("model", {}).get("vocab", {})
                if isinstance(vocab, dict):
                    tokens.update(vocab)
                codes = [c for c in _LANGUAGE_CODES if f"<|{c}|>" in tokens] or ["en"]
            except (OSError, ValueError, TypeError):
                codes = ["en"]
        self.language.clear()
        self.language.addItem(self.t("auto"), None)
        for code in codes:
            self.language.addItem(self.language_name(code), code)
        self.language.setCurrentIndex(max(0, self.language.findData(current)))

    def open_manager(self):
        if self.job.active:
            self.error(self.t("busy"))
            return
        ModelManager(self).exec()

    def open_dictionary_manager(self):
        if self.job.active:
            self.error(self.t("busy"))
            return
        manager = ModelManager(self)
        manager.tabs.setCurrentIndex(1)
        current = self.spell_language(self.table.currentRow())
        if current in manager.dict_codes:
            manager.dictionary_table.selectRow(manager.dict_codes.index(current))
        manager.exec()

    def error(self, message):
        QMessageBox.warning(self, self.t("error"), str(message))

    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, self.t("open"), "",
            "Audio / Video (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wma *.aiff *.aif *.amr *.ape "
            "*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.mpg *.mpeg *.m4v *.ts *.mts *.m2ts *.flv *.3gp);;"
            + self.t("all_files") + " (*)")
        if path:
            self.load_audio(path)

    def load_audio(self, path, relink=False):
        if self.job.active:
            self.error(self.t("busy"))
            return
        if not relink and not self.confirm_save():
            return
        self.pending_source = (str(Path(path).resolve()), relink)
        self.active_kind = "probe"
        self.stage.setText(self.t("probe"))
        self.set_busy(True)
        self.job.start("probe", dict(source=self.pending_source[0]))

    def confirm_save(self):
        if not self.dirty:
            return True
        result = QMessageBox.question(self, self.t("save_project"), self.t("replace_project"),
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        return True

    def open_project(self):
        if self.job.active:
            self.error(self.t("busy"))
            return
        if not self.confirm_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, self.t("project"), "", "Szept (*.json)")
        if path:
            try:
                self.project = Project.loads(Path(path).read_text(encoding="utf-8"))
                self.project_path = Path(path)
                self.reset_history()
                self.render()
                self.set_audio_source()
            except (OSError, ValueError, TypeError, KeyError) as e:
                self.error(e)

    def set_audio_source(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.stop_at = None
        self.seek.setRange(0, 0)
        self.source_label.setText(self.t("empty_hint"))
        if self.project.source and Path(self.project.source).exists():
            self.player.setSource(QUrl.fromLocalFile(self.project.source))
            self.seek.setRange(0, round(self.project.duration * 1000))
            self.source_label.setText(Path(self.project.source).name + " · " + timestamp(self.project.duration, ".") + " · " + self.project.source)
        elif self.project.source:
            self.source_label.setText(self.project.source)
            self.error(self.t("missing_audio"))
            path, _ = QFileDialog.getOpenFileName(self, self.t("open"))
            if path:
                self.load_audio(path, relink=True)

    def save_project(self):
        path = self.project_path
        # Always use Save As, which provides native overwrite confirmation.
        name, _ = QFileDialog.getSaveFileName(self, self.t("save_project"), str(path or Path(self.project.source or "transcript").with_suffix(".json")), "Szept (*.json)")
        if not name:
            return False
        target = Path(name)
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
            if target.exists() and not self.confirm_overwrite(target):
                return False
        try:
            self.protect_source(target)
            atomic_write(target, self.project.dumps())
            self.project_path = target
            self.dirty = False
            self.autosave_path().unlink(missing_ok=True)
            self.saved(target)
            return True
        except (OSError, ValueError) as e:
            self.error(e)
            return False

    def confirm_overwrite(self, path):
        # Qt's localized standard dialog already handles unchanged names.
        return QMessageBox.question(self, self.t("export"), str(path) + "\n" + self.t("overwrite"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def export_file(self):
        formats = "SRT (*.srt);;WebVTT (*.vtt);;TXT (*.txt);;Szept JSON (*.json)"
        name, selected = QFileDialog.getSaveFileName(self, self.t("export"), str(Path(self.project.source or "transcript").with_suffix(".srt")), formats)
        if not name:
            return
        fmt = re.search(r"\*\.(\w+)", selected).group(1)
        path = Path(name)
        if path.suffix.lower() != "." + fmt:
            path = path.with_suffix("." + fmt)
            if path.exists() and not self.confirm_overwrite(path):
                return
        try:
            self.protect_source(path)
            contents = export(self.project, fmt, self.txt_times.isChecked())
            atomic_write(path, contents)
            self.saved(path)
        except ValueError as e:
            self.error(self.t("validation").format(str(e)))
        except OSError as e:
            self.error(e)

    def protect_source(self, path):
        if self.project.source and Path(path).resolve() == Path(self.project.source).resolve():
            raise ValueError(self.t("protect_source"))

    def saved(self, path):
        box = QMessageBox(self)
        box.setWindowTitle(self.t("ready"))
        box.setText(self.t("saved").format(path))
        open_folder = box.addButton(self.t("open_folder"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() == open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve().parent)))

    def start_asr(self):
        if self.job.active:
            return
        if not self.project.source or not Path(self.project.source).exists():
            self.error(self.t("need_audio"))
            return
        if not __import__('math').isfinite(self.project.duration) or self.project.duration <= 0:
            self.error('Najpierw sprawdź długość nagrania / Probe the recording duration first.')
            return
        model = self.model.currentData()
        model_path = self.model_root() / model if model in MODELS else Path(model)
        if not model_ready(model_path):
            self.error(self.t("need_model"))
            self.open_manager()
            return
        if self.project.segments and QMessageBox.question(self, self.t("start"), self.t("restart")) != QMessageBox.StandardButton.Yes:
            return
        self.project.segments = []
        self.project.original_text = ""
        self.project.model = str(model)
        self.project.language = self.language.currentData() or "auto"
        self.project.incomplete = True
        self.record()
        self.render()
        self.active_kind = "asr"
        self.set_busy(True)
        self.progress.setRange(0, 0)
        self.stage.setText(self.t("loading"))
        self.job.start("asr", dict(source=self.project.source, duration=self.project.duration,
                                    model=str(model_path), device=self.device.currentData(), language=self.language.currentData(),
                                    profile=vars(self.project.profile)))
        self.elapsed_timer.start()

    def set_busy(self, busy):
        self.settings_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.segment_edit.setReadOnly(busy)
        self.full_edit.setReadOnly(busy)
        self.table.setEnabled(not busy)

    def cancel_job(self):
        if self.active_kind == "asr":
            self.project.incomplete = True
            self.record()
        self.job.cancel()
        self.stage.setText(self.t("cancelled"))
        self.autosave()

    def job_event(self, event):
        kind = event[0]
        if kind == "metadata":
            path, relink = self.pending_source
            info = event[1]
            if not relink:
                self.project = Project(source=path, duration=info["duration"])
                self.project_path = None
                self.reset_history()
            else:
                self.project.source, self.project.duration = path, info["duration"]
            self.audio_metadata = info
            self.dirty = True
            self.render()
            self.set_audio_source()
            label = f"{Path(path).name} · {timestamp(info['duration'], '.')} · {info['codec']} · {info['rate']} Hz · {info['channels']} ch"
            if info["channels"] > 1:
                label += "\n" + self.t("channels")
            self.source_label.setText(label)
        elif kind == "stage":
            self.stage.setText(self.t(event[1]))
        elif kind == "progress":
            self.progress.setRange(0, 1000)
            self.progress.setValue(round(event[1] * 1000))
        elif kind == "language":
            self.project.language = event[1]
            self.stage.setText(self.t("detected").format(event[1], event[2]))
            self.statusBar().showMessage(self.stage.text())
        elif kind == "segment":
            self.project.segments.append(Segment(**event[1]))
            self.project.original_text += ("\n" if self.project.original_text else "") + event[1]["original"]
            self.dirty = True
            self.append_row(len(self.project.segments) - 1)
        elif kind == "error":
            self.stage.setText(self.t("error"))
            if self.active_kind == "asr" and self.device.currentData() == "cuda":
                if QMessageBox.question(self, self.t("error"), self.t("gpu_error") + "\n\n" + event[1] + ": " + event[2]) == QMessageBox.StandardButton.Yes:
                    self.device.setCurrentIndex(0)
            else:
                self.error(self.t("error") + "\n" + event[1] + ": " + event[2])

    def job_finished(self, success):
        self.set_busy(False)
        self.elapsed_timer.stop()
        self.progress.setRange(0, 1000)
        if self.active_kind == "asr":
            self.project.incomplete = not success
            self.record()
            self.render()
            self.autosave()
            if success:
                self.stage.setText(self.t("completed") if self.project.segments else self.t("no_speech"))
                self.progress.setValue(1000)
        elif success:
            self.stage.setText(self.t("ready"))
        self.active_kind = None

    def show_elapsed(self):
        if self.job.active:
            self.elapsed.setText(self.t("elapsed").format(time.monotonic() - self.job.started))

    def reset_history(self):
        self.history = [self.project.dumps()]
        self.history_index = 0
        self.dirty = False
        self.ignored.clear()
        self.ignored_once.clear()
        self.edit_group = None

    def record(self, edit_key=None):
        state = self.project.dumps()
        if state == self.history[self.history_index]:
            return
        self.history = self.history[:self.history_index + 1]
        now = time.monotonic()
        group = getattr(self, "edit_group", None)
        if edit_key is not None and group and group[0] == edit_key and now - group[1] < .7 and self.history_index > 0:
            self.history[-1] = state
        else:
            self.history.append(state)
        self.edit_group = (edit_key, now) if edit_key is not None else None
        if len(self.history) > 150:
            self.history.pop(0)
        size = sum(sys.getsizeof(value) for value in self.history)
        while size > 64 * 1024 * 1024 and len(self.history) > 2:
            size -= sys.getsizeof(self.history.pop(0))
        self.history_index = len(self.history) - 1
        self.dirty = True
        self.undo_button.setEnabled(self.history_index > 0)
        self.redo_button.setEnabled(False)

    def undo(self):
        if self.job.active or self.history_index <= 0:
            return
        self.history_index -= 1
        self.edit_group = None
        self.ignored_once.clear()
        self.project = Project.loads(self.history[self.history_index])
        self.dirty = True
        self.render()

    def redo(self):
        if self.job.active or self.history_index >= len(self.history) - 1:
            return
        self.history_index += 1
        self.edit_group = None
        self.ignored_once.clear()
        self.project = Project.loads(self.history[self.history_index])
        self.dirty = True
        self.render()

    def append_row(self, index):
        old = self.rendering
        self.rendering = True
        s = self.project.segments[index]
        self.table.setRowCount(max(self.table.rowCount(), index + 1))
        errors, warnings = issues(self.project, index)
        values = [str(index + 1), timestamp(s.start), timestamp(s.end), s.text,
                  " · ".join(self.t(code) for code in errors + warnings)]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col not in (1, 2):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 4 and (errors or warnings):
                dark = self.palette().window().color().lightness() < 128
                item.setForeground(QColor(("#ff91a0" if errors else "#f0c06c") if dark else ("#b4233b" if errors else "#845200")))
            item.setToolTip(text)
            self.table.setItem(index, col, item)
        self.rendering = old

    def render(self):
        row = max(0, min(self.table.currentRow(), len(self.project.segments) - 1))
        self.rendering = True
        self.table.setRowCount(len(self.project.segments))
        for i in range(len(self.project.segments)):
            self.append_row(i)
        self.full_edit.setPlainText("\n".join(s.text.replace("\n", " ") for s in self.project.segments))
        self.table.selectRow(row)
        self.segment_edit.setPlainText(self.project.segments[row].text if self.project.segments else "")
        self.undo_button.setEnabled(self.history_index > 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)
        self.rendering = False
        self.schedule_spell()

    def select_segment(self, row, *args):
        if self.rendering or not 0 <= row < len(self.project.segments):
            return
        self.rendering = True
        self.segment_edit.setPlainText(self.project.segments[row].text)
        self.rendering = False
        self.player.setPosition(round(self.project.segments[row].start * 1000))
        self.stop_at = None
        self.schedule_spell()

    def segment_edited(self):
        if self.rendering:
            return
        row = self.table.currentRow()
        if not 0 <= row < len(self.project.segments):
            return
        s = self.project.segments[row]
        if s.text == self.segment_edit.toPlainText().replace("\n", " "):
            return
        self.ignored_once.clear()
        s.text = self.segment_edit.toPlainText().replace("\n", " ")
        s.review = s.review or s.text != s.original
        s.checked = False
        self.record(edit_key=("segment", row))
        self.append_row(row)
        self.rendering = True
        self.full_edit.setPlainText("\n".join(s.text.replace("\n", " ") for s in self.project.segments))
        self.rendering = False
        self.schedule_spell()

    def full_edited(self):
        if self.rendering:
            return
        self.ignored_once.clear()
        texts = self.full_edit.toPlainText().split("\n")
        if len(texts) != len(self.project.segments):
            self.render()
            return
        for i, text in enumerate(texts):
            s = self.project.segments[i]
            if s.text != text:
                s.text, s.review = text, True
                s.checked = False
                self.append_row(i)
        self.record(edit_key=("full", self.full_edit.textCursor().blockNumber()))
        self.rendering = True
        row = self.table.currentRow()
        if 0 <= row < len(self.project.segments):
            self.segment_edit.setPlainText(self.project.segments[row].text)
        self.rendering = False
        self.schedule_spell()

    def table_edited(self, item):
        if self.rendering or item.column() not in (1, 2):
            return
        try:
            value = parse_time(item.text())
            setattr(self.project.segments[item.row()], "start" if item.column() == 1 else "end", value)
            self.project.segments[item.row()].review=True;self.project.segments[item.row()].checked=False
            self.record()
            self.append_row(item.row())
            if item.row() + 1 < len(self.project.segments):
                self.append_row(item.row() + 1)
        except ValueError:
            self.error(self.t("time"))
            self.append_row(item.row())

    def current_editor(self):
        return self.full_edit if self.tabs.currentIndex() == 1 else self.segment_edit

    def split(self):
        if self.job.active:
            return
        editor = self.current_editor()
        cursor = editor.textCursor()
        row = cursor.blockNumber() if editor is self.full_edit else self.table.currentRow()
        if not 0 <= row < len(self.project.segments):
            return
        # Convert Qt's UTF-16 offset into a Python Unicode index.
        offset = len(cursor.block().text().encode("utf-16-le")[:cursor.positionInBlock() * 2].decode("utf-16-le"))
        s = self.project.segments[row]
        if offset <= 0 or offset >= len(s.text) or (not s.text[offset - 1].isspace() and not s.text[offset].isspace()):
            self.error(self.t("invalid_split"))
            return
        try:
            self.project.segments[row:row + 1] = split_segment(s, offset)
            self.record()
            self.render()
        except ValueError:
            self.error(self.t("invalid_split"))

    def merge(self):
        if self.job.active:
            return
        row = self.full_edit.textCursor().blockNumber() if self.tabs.currentIndex() == 1 else self.table.currentRow()
        if not 0 <= row < len(self.project.segments) - 1:
            return
        a, b = self.project.segments[row:row + 2]
        merged = Segment(a.start, b.end, a.text.rstrip() + " " + b.text.lstrip(),
                         a.original + " " + b.original, a.words + b.words, True, a.spell_language)
        self.project.segments[row:row + 2] = [merged]
        self.record()
        self.render()

    def find_next(self):
        self.tabs.setCurrentIndex(1)
        text = self.find_input.text()
        if text and not self.full_edit.find(text):
            self.full_edit.moveCursor(QTextCursor.MoveOperation.Start)
            self.full_edit.find(text)

    def replace_all(self):
        if self.job.active or not self.find_input.text():
            return
        for s in self.project.segments:
            value = s.text.replace(self.find_input.text(), self.replace_input.text())
            if value != s.text:
                s.text, s.review = value, True
                s.checked = False
        self.record()
        self.render()

    def toggle_play(self):
        self.stop_at = None
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def listen_segment(self):
        row = self.full_edit.textCursor().blockNumber() if self.tabs.currentIndex() == 1 else self.table.currentRow()
        if 0 <= row < len(self.project.segments):
            s = self.project.segments[row]
            self.player.setPosition(round(s.start * 1000))
            self.stop_at = round(s.end * 1000)
            self.player.play()

    def seek_to(self, value):
        self.stop_at = None
        self.player.setPosition(value)

    def player_position(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.clock.setText(timestamp(position / 1000, ".")[:-4] + " / " + timestamp(self.project.duration, ".")[:-4])
        if self.stop_at is not None and position >= self.stop_at:
            self.player.pause()
            self.stop_at = None

    def spell_language(self, index=-1):
        if 0 <= index < len(self.project.segments) and self.project.segments[index].spell_language:
            language = self.project.segments[index].spell_language
        else:
            selected = self.spell.currentData() if hasattr(self, "spell") else "auto"
            language = self.project.language if selected == "auto" else selected
        if hasattr(self, "spell") and self.spell.currentData() == "off":
            return "off"
        return resolve(self.data_root, language, getattr(self, "dictionary_codes", None))

    def refresh_spell_languages(self):
        current = self.spell.currentData() or "auto"
        present = installed(data_dir())
        self.dictionary_codes = present
        self.spell.blockSignals(True)
        self.spell.clear()
        self.spell.addItem(self.t("follow"), "auto")
        self.spell.addItem(self.t("spell_off"), "off")
        for code in list(PACKS) + sorted(present - set(PACKS)):
            suffix = " ✓" if code in present or code == "en" else " ↓"
            self.spell.addItem(self.dictionary_name(code) + suffix, code)
        self.spell.setCurrentIndex(max(0, self.spell.findData(current)))
        self.spell.blockSignals(False)

    def set_segment_language(self):
        if self.job.active:
            return
        language = self.spell.currentData()
        editor = self.current_editor()
        if editor is self.full_edit:
            cursor = editor.textCursor()
            first = editor.document().findBlock(cursor.selectionStart()).blockNumber()
            last = editor.document().findBlock(max(cursor.selectionStart(), cursor.selectionEnd() - 1)).blockNumber()
            indices = range(first, last + 1)
        else:
            indices = [self.table.currentRow()]
        for i in indices:
            if 0 <= i < len(self.project.segments):
                self.project.segments[i].spell_language = "" if language == "auto" else language
        self.record()
        self.schedule_spell()

    def restart_spelling(self):
        self.stop_spell_worker("spell")
        self.stop_spell_worker("suggest")
        ctx = mp.get_context("spawn")
        self.spell_commands, self.spell_output = ctx.Queue(), ctx.Queue()
        self.spell_process = ctx.Process(target=spell_loop, args=(str(data_dir()), self.spell_commands, self.spell_output), daemon=True)
        self.spell_process.start()
        self.spell_cache, self.suggestion_cache = {}, {}
        self.spell_requests = {}
        self.spell_errors = {}
        self.spell_pending = False
        self.spell_failed = False
        self.suggestion_pending = None
        self.suggestion_menu = None
        self.refresh_spell_languages()
        self.poll_timer.start()
        self.rehighlight()
        self.schedule_spell()

    def stop_spell_worker(self, prefix):
        process = getattr(self, prefix + "_process", None)
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        if process.is_alive():
            process.kill()
            process.join(timeout=3)
        process.close()
        for name in ("_commands", "_output"):
            getattr(self, prefix + name).close()
        setattr(self, prefix + "_process", None)

    def retry_spelling(self):
        self.restart_spelling()

    def update_spell_status(self):
        if self.spell_failed:
            self.spell_status.setText(self.t("spell_failed"))
            return
        codes = {self.spell_language(i) for i in range(len(self.project.segments))} or {self.spell_language()}
        codes.discard("off")
        if not codes:
            self.spell_status.setText(self.t("spell_off"))
            return
        missing = [c for c in sorted(codes) if self.spell_errors.get(c, {}).get("kind") == "missing"]
        invalid = [c for c in sorted(codes) if self.spell_errors.get(c, {}).get("kind") == "invalid"]
        if missing or invalid:
            parts = ([self.t("missing_dict") + " (" + ", ".join(missing) + ")"] if missing else [])
            if invalid:
                parts.append(self.t("invalid_dictionary") + " (" + ", ".join(invalid) + ")")
            self.spell_status.setText(" · ".join(parts))
        elif self.spell_pending:
            self.spell_status.setText(self.t("checking"))
        else:
            self.spell_status.setText(self.t("spell_ready") + " [" + ", ".join(sorted(codes)) + "]")

    def schedule_spell(self):
        self.rehighlight()
        self.spell_timer.start()

    def check_spelling(self):
        if not getattr(self, "spell_process", None) or self.spell_failed:
            return
        if self.spell_pending:
            self.spell_timer.start()
            return
        self.spell_generation += 1
        groups = {}
        for i, s in enumerate(self.project.segments):
            language = self.spell_language(i)
            if language == "off":
                continue
            groups.setdefault(language, set()).update(word for _, _, word in word_spans(s.text))
        self.spell_requests = {}
        for language, words in groups.items():
            self.custom_words[language] = user_words(data_dir(), language)
            unknown = words - self.spell_cache.get(language, {}).keys()
            if unknown and language not in self.spell_errors:
                self.spell_requests[language] = self.spell_generation
                self.spell_commands.put((self.spell_generation, "check", language, "\n".join(unknown)))
        self.spell_pending = bool(self.spell_requests)
        self.spell_started = time.monotonic()
        self.update_spell_status()
        self.rehighlight()

    def request_suggestions(self, language, word):
        if language == "off":
            return
        if self.suggestion_pending:
            self.stop_spell_worker("suggest")
        if not getattr(self, "suggest_process", None):
            ctx = mp.get_context("spawn")
            self.suggest_commands, self.suggest_output = ctx.Queue(), ctx.Queue()
            self.suggest_process = ctx.Process(target=spell_loop, args=(str(data_dir()), self.suggest_commands, self.suggest_output), daemon=True)
            self.suggest_process.start()
        token = getattr(self, "suggest_generation", 0) + 1
        self.suggest_generation = token
        self.suggestion_pending = dict(token=token, language=language, word=word, started=time.monotonic())
        self.suggest_commands.put((token, "suggest", language, word))

    def replace_suggestion(self, editor, cursor, word, revision, replacement):
        from shiboken6 import isValid
        if isValid(editor) and not editor.isReadOnly() and editor.text_generation == revision and cursor.selectedText() == word:
            cursor.insertText(replacement)

    def render_suggestions(self, language, word):
        pending = self.suggestion_menu
        if not pending or pending[:2] != (language, word):
            return
        from shiboken6 import isValid
        _, _, menu, cursor, revision, editor = pending
        if not isValid(menu) or not isValid(editor):
            self.suggestion_menu = None
            return
        menu.clear()
        values = self.suggestion_cache.get((language, word), [])
        for value in values:
            menu.addAction(value, lambda replacement=value: self.replace_suggestion(editor, QTextCursor(cursor), word, revision, replacement))
        if not values:
            menu.addAction(self.t("no_suggestions")).setEnabled(False)

    def poll_spell(self):
        process = getattr(self, "spell_process", None)
        if process and (not process.is_alive() or (self.spell_pending and time.monotonic() - self.spell_started > 30)):
            self.stop_spell_worker("spell")
            self.spell_failed = True
            self.spell_pending = False
            self.update_spell_status()
        for _ in range(20) if getattr(self, "spell_process", None) else []:
            try:
                token, op, language, result = self.spell_output.get_nowait()
            except queue.Empty:
                break
            if op in {"check", "check_error"}:
                if self.spell_requests.get(language) != token:
                    continue
                self.spell_requests.pop(language, None)
                self.spell_pending = bool(self.spell_requests)
                if op == "check":
                    self.spell_cache.setdefault(language, {}).update(result)
                    self.spell_errors.pop(language, None)
                else:
                    self.spell_cache.pop(language, None)
                    self.spell_errors[language] = result
                self.update_spell_status()
                self.rehighlight()
        for _ in range(20) if getattr(self, "suggest_process", None) else []:
            try:
                token, op, language, result = self.suggest_output.get_nowait()
            except queue.Empty:
                break
            pending = self.suggestion_pending
            if not pending or pending["token"] != token or pending["language"] != language:
                continue
            word = pending["word"]
            self.suggestion_cache[(language, word)] = result if isinstance(result, list) else []
            self.render_suggestions(language, word)
            if op in {"suggest", "suggest_error"}:
                self.suggestion_pending = None
        if self.suggestion_pending and (time.monotonic() - self.suggestion_pending["started"] > 8 or not self.suggest_process.is_alive()):
            pending = self.suggestion_pending
            self.suggestion_cache.setdefault((pending["language"], pending["word"]), [])
            self.render_suggestions(pending["language"], pending["word"])
            self.stop_spell_worker("suggest")
            self.suggestion_pending = None
            self.statusBar().showMessage(self.t("suggest_timeout"), 8000)

    def rehighlight(self):
        previous = self.rendering
        self.rendering = True
        try:
            self.segment_edit.highlighter.rehighlight()
            self.full_edit.highlighter.rehighlight()
        finally:
            self.rendering = previous

    def ignore_word(self, language, word):
        self.ignored.add((language, canonical(word).casefold()))
        self.rehighlight()

    def add_user_word(self, language, word):
        try:
            add_word(data_dir(), language, word)
            self.custom_words[language] = user_words(data_dir(), language)
            self.rehighlight()
        except OSError as e:
            self.error(e)

    def autosave_path(self):
        return self.recovery.path

    def autosave(self):
        if self.dirty:
            try:
                atomic_write(self.autosave_path(), self.project.dumps())
            except OSError as e:
                self.statusBar().showMessage(self.t("error") + ": " + str(e))

    def recover(self):
        candidates = self.recovery.candidates()
        if candidates:
            p = candidates[0]
            if QMessageBox.question(self, self.t("project"), self.t("recover")) == QMessageBox.StandardButton.Yes:
                try:
                    if not self.recovery.claim(p):
                        raise ValueError('Kopia jest używana / Recovery is in use')
                    self.project = Project.loads(p.read_text(encoding="utf-8"))
                    self.reset_history()
                    self.dirty = True
                    self.render()
                    self.set_audio_source()
                    self.autosave()
                except (OSError, ValueError, TypeError, KeyError) as e:
                    self.error(e)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_audio(urls[0].toLocalFile())

    def closeEvent(self, event):
        if self.job.active:
            if QMessageBox.question(self, self.t("cancel"), self.t("stop_close")) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.cancel_job()
        if not self.confirm_save():
            event.ignore()
            return
        self.player.stop()
        for key, value in (("recording_language", self.language.currentData() or "auto"),
                           ("selected_model", self.model.currentData()), ("device", self.device.currentData()),
                           ("spell", self.spell.currentData())):
            self.settings.setValue(key, value)
        self.spell_timer.stop()
        self.poll_timer.stop()
        self.autosave_timer.stop()
        self.stop_spell_worker("spell")
        self.stop_spell_worker("suggest")
        if hasattr(self, 'translator'):
            QApplication.instance().removeTranslator(self.translator)
        self.autosave_path().unlink(missing_ok=True)
        self.recovery.close()
        event.accept()
