"""Translate a caption track with local Ollama into a new track with the same timings."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from PySide6.QtCore import QSettings, QProcess, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
                               QPushButton, QSpinBox, QProgressBar)
from core.ai.ollama import Ollama, local_url, LANGUAGES
from core.projects.model import Track, Segment
from ui.jobs import Job


def translated_track(source, translations, language):
    """New track: same times and style, translated text, no word timings (they belonged to the original)."""
    texts = {item['id']: item['text'] for item in translations}
    segments = [Segment(start=s.start, end=s.end, text=texts.get(i, s.text), language=language,
                        timed=s.timed, review=bool(s.text.strip()) and i not in texts)
                for i, s in enumerate(source.segments)]
    return Track(name=f'{source.name} · {language.upper()}', segments=segments, style=copy.deepcopy(source.style))


class TranslateDialog(QDialog):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.workspace = workspace; self.editor = workspace.editor
        self.process = None; self.temp = None; self.request = 0; self.closed = False; self.context = None
        self.settings = QSettings('LocalTools', 'SubtitleStudioAI')
        self.setWindowTitle('Tłumaczenie napisów · Ollama / Caption translation · Ollama')
        self.resize(640, 360)
        layout = QVBoxLayout(self)
        note = QLabel('Tekst trafia tylko do lokalnej Ollamy. Tłumaczenie tworzy NOWĄ ścieżkę z tymi samymi czasami; '
                      'oryginał zostaje bez zmian.\nLocal Ollama only. Translation creates a NEW track with the same '
                      'timings; the original is unchanged.')
        note.setWordWrap(True); layout.addWidget(note)
        form = QFormLayout(); layout.addLayout(form)
        self.url = QLineEdit(str(self.settings.value('url', 'http://127.0.0.1:11434')))
        form.addRow('Lokalny serwer / Local server', self.url)
        self.model = QComboBox(); bar = QHBoxLayout(); bar.addWidget(self.model, 1)
        self.refresh_button = QPushButton('Odśwież modele / Refresh models')
        self.refresh_button.clicked.connect(self.refresh_models); bar.addWidget(self.refresh_button)
        form.addRow('Model', bar)
        self.track = QComboBox()
        for track in self.editor.project.tracks:
            self.track.addItem(f'{track.name} · {len(track.segments)}', track.track_id)
        self.track.setCurrentIndex(min(self.editor.active_track, self.track.count()-1))
        form.addRow('Ścieżka źródłowa / Source track', self.track)
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(f'{name} ({code})', code)
        self.language.setCurrentIndex(max(0, self.language.findData(
            str(self.settings.value('translation_language', 'en')))))
        form.addRow('Język docelowy / Target language', self.language)
        self.timeout = QSpinBox(); self.timeout.setRange(30, 600); self.timeout.setValue(180)
        self.timeout.setSuffix(' s / partia / batch'); form.addRow('Limit czasu / Timeout', self.timeout)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self.start = QPushButton('Przetłumacz / Translate'); self.start.clicked.connect(self.begin); bar.addWidget(self.start)
        self.cancel = QPushButton('Anuluj / Cancel'); self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_job); bar.addWidget(self.cancel)
        self.progress = QProgressBar(); layout.addWidget(self.progress)
        self.message = QLabel(); self.message.setWordWrap(True); layout.addWidget(self.message)
        self.controls = [self.url, self.model, self.refresh_button, self.track, self.language, self.timeout, self.start]
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(250)
        self.refresh_models()

    def refresh_models(self):
        if self.process:
            return
        try:
            client = Ollama(self.url.text())
        except ValueError as error:
            self.message.setText(str(error)); return
        self.request += 1; token = self.request; self.start.setEnabled(False); self.model.clear()
        self.message.setText('Sprawdzanie lokalnych modeli… / Checking local models…')
        def ready(models):
            if token != self.request or self.closed:
                return
            for model in models:
                self.model.addItem(f"{model['name']} · {model['size']/1e9:.1f} GB", model['name'])
            self.model.setCurrentIndex(max(0, self.model.findData(str(self.settings.value('model', '')))))
            self.start.setEnabled(bool(models))
            self.message.setText(f'Lokalne modele / Local models: {len(models)}' if models else
                                 'Brak lokalnych modeli tekstowych. / No local text models.')
        def failed(error):
            if token == self.request and not self.closed:
                self.message.setText(str(error))
        self.editor.pool.start(Job(client.models, ready, failed))

    def begin(self):
        if self.process:
            return
        try:
            url = local_url(self.url.text()); model = self.model.currentData(); language = self.language.currentData()
            if not model:
                raise ValueError('Wybierz lokalny model / Select a local model')
            track = next((t for t in self.editor.project.tracks if t.track_id == self.track.currentData()), None)
            if track is None:
                raise ValueError('Ścieżka nie istnieje / The track no longer exists')
            captions = [dict(id=i, text=s.text) for i, s in enumerate(track.segments) if s.text.strip()]
            if not captions:
                raise ValueError('Ścieżka nie zawiera tekstu / The track has no text')
            if any(len(c['text']) > 3000 for c in captions):
                raise ValueError('Podziel segmenty dłuższe niż 3000 znaków / Split captions longer than 3000 characters')
            # Snapshot the source so edits made meanwhile cannot misalign texts and times.
            self.context = (track.track_id, copy.deepcopy(track), language)
            self.temp = tempfile.TemporaryDirectory(prefix='subtitle-translate-'); folder = Path(self.temp.name)
            self.status = folder/'status.json'; self.cancel_path = folder/'cancel'; config = folder/'job.json'
            config.write_text(json.dumps(dict(mode='translate', url=url, model=model, captions=captions,
                language=language, timeout=self.timeout.value()), ensure_ascii=False), encoding='utf-8')
            self.settings.setValue('url', url); self.settings.setValue('model', model)
            self.settings.setValue('translation_language', language)
            for widget in self.controls:
                widget.setEnabled(False)
            self.cancel.setEnabled(True); self.progress.setValue(0)
            self.message.setText(f'Tłumaczenie {len(captions)} napisów… / Translating {len(captions)} captions…')
            self.process = QProcess(self); self.process.finished.connect(self.finish)
            self.process.errorOccurred.connect(
                lambda error: self.finish(1, None) if error == QProcess.ProcessError.FailedToStart else None)
            args = ['--ollama-correct', str(config), str(self.cancel_path), str(self.status)]
            if not getattr(sys, 'frozen', False):
                args.insert(0, str(Path(__file__).resolve().parents[1]/'main.py'))
            self.process.start(sys.executable, args)
        except (ValueError, OSError) as error:
            self.message.setText(str(error))

    def read_status(self):
        try:
            return json.loads(self.status.read_text(encoding='utf-8'))
        except (ValueError, OSError, AttributeError):
            return {}

    def poll(self):
        if self.process:
            status = self.read_status(); self.progress.setValue(status.get('percent', self.progress.value()))
            if status.get('stage'):
                self.message.setText(status['stage'])

    def finish(self, code, status):
        if not self.process:
            return
        result = self.read_status(); cancelled = self.cancel_path.exists()
        if code == 0 and result.get('done') and not cancelled:
            try:
                self.apply(result['translations'])
                self.progress.setValue(100)
            except (ValueError, KeyError, TypeError) as error:
                self.message.setText(str(error))
        else:
            self.message.setText('Anulowano / Cancelled' if cancelled else result.get('error', 'Błąd Ollamy / Ollama failed'))
        for widget in self.controls:
            widget.setEnabled(True)
        self.cancel.setEnabled(False)
        self.process.deleteLater(); self.process = None; self.temp.cleanup(); self.temp = None

    def apply(self, translations):
        track_id, source, language = self.context
        current = next((t for t in self.editor.project.tracks if t.track_id == track_id), None)
        if current is None or [(s.start, s.end) for s in current.segments] != [(s.start, s.end) for s in source.segments]:
            raise ValueError('Ścieżka zmieniła się w trakcie tłumaczenia. Uruchom ponownie. / '
                             'The track changed during translation; run it again.')
        track = translated_track(source, translations, language)
        self.editor.checkpoint()
        self.editor.project.tracks.append(track)
        self.editor.active_track = len(self.editor.project.tracks)-1
        self.editor.active_logo = self.editor.active_banner = -1
        self.editor.refresh()
        self.message.setText(f'Dodano ścieżkę „{track.name}”. / Added track “{track.name}”.')

    def cancel_job(self):
        if self.process:
            self.cancel_path.touch()

    def closeEvent(self, event):
        if self.process:
            self.message.setText('Najpierw anuluj tłumaczenie. / Cancel the translation first.')
            event.ignore(); return
        self.closed = True
        super().closeEvent(event)
