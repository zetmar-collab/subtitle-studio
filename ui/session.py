"""Szept keeps its editing history; the enclosing workspace owns persistence."""
from srtstudio.ui import Window
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFileDialog
from pathlib import Path
import json


class IntegratedSpeechWindow(Window):
    def __init__(self, workspace):
        self.workspace = workspace
        super().__init__()

    def save_project(self):
        return self.workspace.editor.save_project()

    def build_ui(self):
        super().build_ui()
        for action in self.shortcut_actions:
            if action.shortcut().toString()=='Ctrl+S':action.setShortcut(QKeySequence())
        self.menuBar().addAction('Pisownia AI · Ollama',self.workspace.show_ai)

    def open_project(self):
        if self.job.active:
            self.error(self.t('busy'));return
        path,_=QFileDialog.getOpenFileName(self,'Sesja lub Szept / Session or Szept','','JSON (*.json)')
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
