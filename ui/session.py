"""Szept keeps its editing history; the enclosing workspace owns persistence."""
from srtstudio.ui import Window
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFileDialog, QScrollArea, QLabel, QComboBox, QHBoxLayout
from pathlib import Path
import json


class IntegratedSpeechWindow(Window):
    def __init__(self, workspace):
        self.workspace = workspace
        super().__init__()
        self.setMinimumSize(0, 0)

    def save_project(self):
        return self.workspace.editor.save_project()

    def build_ui(self):
        self.ui_language = self.workspace.editor.project.language
        super().build_ui()
        for action in self.shortcut_actions:
            if action.shortcut().toString()=='Ctrl+S':action.setShortcut(QKeySequence())
        self.menuBar().addAction(self.workspace.editor.tr_text('Korekta AI', 'AI proofreading'),self.workspace.show_ai)
        for label in self.findChildren(QLabel):
            if label.objectName() == 'brand':
                label.setText(self.workspace.editor.tr_text('Rozpoznawanie mowy', 'Speech recognition'))
            elif label.objectName() == 'badge':
                label.hide()
        root = self.takeCentralWidget()
        root.layout().setContentsMargins(12, 8, 12, 8)
        root.layout().setSpacing(8)
        # Keep the editing commands and language options on separate rows so
        # larger text does not push the primary actions beyond the viewport.
        for index in range(root.layout().count()):
            row = root.layout().itemAt(index).layout()
            if row and row.indexOf(self.undo_button) >= 0:
                language_row = QHBoxLayout()
                while row.count() > 5:
                    language_row.addItem(row.takeAt(5))
                root.layout().insertLayout(index + 1, language_row)
                break
        for combo in (self.language, self.model, self.device, self.spell):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.device.setItemText(0, self.workspace.editor.tr_text('Procesor (CPU)', 'Processor (CPU)'))
        self.device.setItemText(1, self.workspace.editor.tr_text('Karta NVIDIA (GPU)', 'NVIDIA graphics (GPU)'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        self.seek.setAccessibleName(self.workspace.editor.tr_text('Pozycja odtwarzania', 'Playback position'))
        self.speed.setAccessibleName(self.workspace.editor.tr_text('Prędkość odtwarzania', 'Playback speed'))
        for widget, key in [(self.language, 'language'), (self.model, 'model'), (self.device, 'device'),
                            (self.find_input, 'find'), (self.replace_input, 'replace')]:
            widget.setAccessibleName(self.t(key))

    def apply_theme(self):
        from ui.appearance import apply_appearance
        editor = self.workspace.editor
        apply_appearance(self, editor.project.theme, editor.interface_font_size())

    def error(self, message):
        self.workspace.editor.error(message)

    def open_project(self):
        if self.job.active:
            self.error(self.t('busy'));return
        path,_=QFileDialog.getOpenFileName(self,self.workspace.editor.tr_text('Otwórz projekt', 'Open project'),'','JSON (*.json)')
        if not path:return
        try:
            source=Path(path)
            if source.stat().st_size>40_000_000:raise ValueError('Projekt jest zbyt duży / Project is too large')
            text=source.read_text(encoding='utf-8');data=json.loads(text)
            if data.get('version') in (1,2):
                self.workspace.editor.open_project(path);return
            from srtstudio.project import Project
            project=Project.loads(text)
            if not self.confirm_save():return
            self.project=project;self.project_path=None;self.audio_metadata=None
            self.reset_history();self.dirty=True;self.render();self.set_audio_source();self.autosave()
        except (ValueError,OSError,TypeError,KeyError) as error:self.error(error)

    def autosave(self):
        self.workspace.editor.autosave()

    def recover(self):
        # Only the migration of a pre-session Szept recovery uses this path.
        if self.workspace.editor.project.transcript is None:
            super().recover()
