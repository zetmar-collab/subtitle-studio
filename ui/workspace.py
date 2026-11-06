"""One application window with video editing and the integrated Szept workspace."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction,QKeySequence
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTabWidget, QPushButton, QLabel, QMessageBox)
from ui.window import Window
from core.subtitles.transcription import to_track, to_transcript
import copy
import json


class Workspace(QMainWindow):
    def __init__(self):
        super().__init__()
        self.editor = Window()
        self.transcription = None
        self.editor.before_save = self.capture_session
        self.editor.session_dirty = lambda: bool(self.transcription and self.transcription.dirty)
        self.editor.session_saved = self.session_saved
        self.editor.session_reset = self.reset_transcript
        self.editor.project_loaded = self.restore_session
        self.editor.can_replace = self.can_replace
        self.editor.spell_delegate = self.spell_track
        self.workflow = None
        self.review_dialog = None
        self.queue = None
        self.editor.setWindowFlags(Qt.WindowType.Widget)
        self.setWindowIcon(self.editor.windowIcon())
        self.setWindowTitle('Subtitle Studio + Szept')
        self.resize(1540, 1020)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        for label, callback in [
            ('Transkrybuj bieżący film / Transcribe video', self.transcribe_video),
            ('Napisy → transkrypcja / Edit transcript', self.send_to_transcript),
            ('Transkrypcja → film / Send captions to video', self.send_to_editor),
            ('Pisownia AI · Ollama',self.show_ai),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.editor, 'Film i napisy / Video editor')
        placeholder = QWidget()
        empty = QVBoxLayout(placeholder)
        hint = QLabel('Szept — lokalna transkrypcja, edytor tekstu i słowniki.\n'
                      'Szept — local transcription, text editor and dictionaries.')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(hint)
        self.tabs.addTab(placeholder, 'Transkrypcja / Transcription')
        self.tabs.currentChanged.connect(self.switch_tab)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.editor.windowTitleChanged.connect(lambda title: self.setWindowTitle(title + ' + Szept'))
        project_menu=self.menuBar().addMenu('Projekt / Project')
        keys={'Ctrl+N','Ctrl+Shift+O','Ctrl+S'}
        for action in self.editor.findChildren(QAction):
            if action.shortcut().toString() in keys:action.setShortcut(QKeySequence())
        for label,callback,key in [('Nowa sesja / New session',self.editor.new_project,'Ctrl+N'),
                               ('Otwórz sesję / Open session',self.editor.open_project,'Ctrl+Shift+O'),
                               ('Zapisz sesję / Save session',self.editor.save_project,'Ctrl+S'),
                               ('Zapisz sesję jako / Save session as',self.save_as,'')]:
            action=project_menu.addAction(label,callback)
            if key:action.setShortcut(QKeySequence(key));self.addAction(action)
        tools=self.menuBar().addMenu('Narzędzia / Tools')
        for label,callback in [('Film → napisy → MP4',self.show_workflow),
                               ('Pisownia AI · Ollama',self.show_ai),
                               ('Napraw synchronizację / Repair timing',self.show_repair),
                               ('Słowa na fali audio / Word alignment',self.editor.words_dialog),
                               ('Fragmenty do sprawdzenia / Review queue',self.show_review),
                               ('Kolejka eksportów / Export queue',self.show_queue),
                               ('Pokaz zdjęć i klipów / Slideshow',self.show_slideshow)]:
            tools.addAction(label,callback)

    def speech(self):
        if self.transcription is None:
            from ui.session import IntegratedSpeechWindow
            widget = IntegratedSpeechWindow(self)
            widget.setWindowFlags(Qt.WindowType.Widget)
            self.transcription = widget
            old = self.tabs.widget(1)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(1)
            self.tabs.insertTab(1, widget, 'Transkrypcja / Transcription')
            self.tabs.setCurrentIndex(1)
            self.tabs.blockSignals(False)
            old.deleteLater()
        return self.transcription

    def switch_tab(self, index):
        if index == 1:
            self.editor.player.pause()
            try:
                self.speech()
            except Exception as error:
                self.tabs.setCurrentIndex(0)
                self.editor.error(error)
        elif self.transcription:
            self.transcription.player.pause()

    def transcribe_video(self):
        source = self.editor.project.video
        if not source:
            self.editor.error('Najpierw otwórz film / Open a video first.')
            return
        try:
            speech = self.speech()
            if speech.job.active:
                raise ValueError('Zakończ lub anuluj bieżące zadanie / Finish or cancel the current job.')
            self.tabs.setCurrentIndex(1)
            self.editor.player.pause()
            if speech.project.source == source and speech.project.duration > 0:
                speech.start_asr()
                return
            if not getattr(self, '_video_probe_connected', False):
                speech.job.finished.connect(self.video_probe_finished)
                self._video_probe_connected = True
            self._pending_video_asr = (source, self.editor.project)
            speech.load_audio(source)
            if not speech.job.active:
                self._pending_video_asr = None
        except Exception as error:
            self.editor.error(error)

    def video_probe_finished(self, success):
        pending = getattr(self, '_pending_video_asr', None)
        self._pending_video_asr = None
        if not pending or not success:
            return
        source, project = pending
        speech = self.speech()
        if self.editor.project is project and project.video == source and speech.project.source == source:
            speech.start_asr()

    def send_to_transcript(self):
        try:
            self._transfer_request=getattr(self,'_transfer_request',0)+1
            request=self._transfer_request
            source_project=self.editor.project
            track = self.editor.track()
            source = self.editor.project.video
            if not source and Path(track.source).suffix.lower() in {
                    '.wav','.mp3','.flac','.m4a','.aac','.ogg','.opus','.wma',
                    '.aiff','.aif','.amr','.ape','.mp4','.mov','.mkv','.avi','.webm',
                    '.wmv','.mpg','.mpeg','.m4v','.ts','.mts','.m2ts','.flv','.3gp'}:
                source = track.source
            duration = self.editor.info['duration']
            if not duration and self.transcription and self.transcription.project.source == source:
                duration = round(self.transcription.project.duration * 1000)
            if source and duration <= 0:
                from core.media.tools import probe_audio
                from ui.jobs import Job
                speech = self.speech()
                if speech.job.active:
                    raise ValueError('Zakończ zadanie / Finish the current job first.')
                def ready(info):
                    if request == self._transfer_request and self.editor.project is source_project and self.editor.track() is track:
                        try:self._send_transcript(to_transcript(track,source,info['duration']))
                        except ValueError as error:self.editor.error(error)
                self.editor.pool.start(Job(lambda: probe_audio(source),ready,
                    lambda error:self.editor.error(error) if request==self._transfer_request and self.editor.project is source_project else None))
                return
            project = to_transcript(track, source, duration)
            self._send_transcript(project)
        except Exception as error:
            self.editor.error(error)

    def _send_transcript(self, project):
        try:
            speech = self.speech()
            if speech.job.active:
                raise ValueError('Zakończ zadanie transkrypcji / Finish the transcription job first.')
            if not speech.confirm_save():
                return
            if speech.project.source == project.source:
                project.model = speech.project.model
                project.profile = copy.deepcopy(speech.project.profile)
                project.incomplete = speech.project.incomplete
                project.original_text = speech.project.original_text or project.original_text
            speech.project = project
            speech.project_path = None
            speech.audio_metadata = None
            speech.reset_history()
            speech.dirty = True
            speech.render()
            speech.set_audio_source()
            self.editor.project.linked_track = self.editor.track().track_id
            speech.autosave()
            self.editor.player.pause()
            self.tabs.setCurrentIndex(1)
        except Exception as error:
            self.editor.error(error)

    def send_to_editor(self):
        try:
            speech = self.speech()
            if speech.job.active:
                raise ValueError('Zakończ zadanie transkrypcji / Finish the transcription job first.')
            if self.editor.export_process:
                raise ValueError('Zakończ eksport filmu / Finish exporting the video first.')
            track = to_track(speech.project)
            source, video = speech.project.source, self.editor.project.video
            if source and video and Path(source).resolve() != Path(video).resolve():
                answer = QMessageBox.question(self, 'Źródło napisów / Caption source',
                    'Nagranie transkrypcji różni się od bieżącego filmu.\n'
                    'Dodać napisy do bieżącego filmu bez przesuwania czasów?\n\n'
                    'The transcript uses another recording. Add captions to the current video at their original times?')
                if answer != QMessageBox.StandardButton.Yes:
                    return
            if video and any(s.end > self.editor.info['duration'] for s in track.segments):
                raise ValueError('Napisy wychodzą poza film. Popraw czasy lub otwórz właściwy film.\n'
                                 'Captions exceed the video duration. Correct timing or open the matching video.')
            linked = next((t for t in self.editor.project.tracks
                           if t.track_id == self.editor.project.linked_track and t.source == source), None)
            if linked:
                old = linked.segments
                changed = sum(a.text != b.text or (a.start,a.end)!=(b.start,b.end)
                              for a,b in zip(old,track.segments)) + abs(len(old)-len(track.segments))
                answer = QMessageBox.question(self,'Aktualizacja / Update',
                    f'Powiązana ścieżka / Linked track: {linked.name}\n'
                    f'Segmenty / Captions: {len(old)} → {len(track.segments)}; zmiany / changes: {changed}\n'
                    'Tak / Yes: aktualizuj, zachowując styl / update and keep style.\n'
                    'Nie / No: dodaj osobną ścieżkę / add a separate track.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if answer == QMessageBox.StandardButton.Cancel:
                    return
                if answer == QMessageBox.StandardButton.No:
                    linked = None
            self.editor.checkpoint()
            if linked:
                linked.segments = track.segments
                self.editor.active_track = self.editor.project.tracks.index(linked)
            else:
                self.editor.project.tracks.append(track)
                self.editor.active_track = len(self.editor.project.tracks)-1
            self.editor.project.linked_track = self.editor.track().track_id
            self.editor.active_logo = -1
            self.editor.refresh()
            self.editor.layers.setCurrentRow(self.editor.active_track + 1)
            speech.player.pause()
            self.tabs.setCurrentIndex(0)
            self.editor.statusBar().showMessage('Dodano ścieżkę z czasami słów / Added a caption track with word timing.', 12000)
            return True
        except Exception as error:
            self.editor.error(error)
            return False

    def show_workflow(self):
        if self.workflow is None:
            from ui.workflow import WorkflowDock
            self.workflow=WorkflowDock(self)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.workflow)
        self.workflow.show()

    def show_repair(self):
        from ui.repair import RepairDialog
        dialog=RepairDialog(self.editor);dialog.exec();dialog.deleteLater()

    def show_review(self):
        from ui.review import ReviewDialog
        if self.review_dialog is None:self.review_dialog=ReviewDialog(self)
        self.review_dialog.show();self.review_dialog.raise_()

    def show_queue(self):
        from ui.export_queue import ExportQueueDialog
        if not hasattr(self,'queue_dialog'):self.queue_dialog=ExportQueueDialog(self)
        self.queue_dialog.show();self.queue_dialog.raise_()

    def show_slideshow(self):
        from ui.slideshow import SlideshowDialog
        dialog=SlideshowDialog(self.editor);dialog.exec();dialog.deleteLater()

    def show_ai(self):
        from ui.ollama import OllamaDialog
        if not hasattr(self,'ai_dialog'):self.ai_dialog=OllamaDialog(self)
        self.ai_dialog.prepare(self.tabs.currentIndex())
        self.ai_dialog.show();self.ai_dialog.raise_()

    def can_replace(self):
        if self.transcription and self.transcription.job.active:
            self.editor.error('Zakończ lub anuluj zadanie transkrypcji / Finish or cancel transcription first.')
            return False
        return True

    def save_as(self):
        old=self.editor.path;self.editor.path=None
        if not self.editor.save_project():self.editor.path=old

    def spell_track(self):
        track=self.editor.track()
        if all(segment.timed and 0<=segment.start<segment.end for segment in track.segments):
            self.send_to_transcript();return
        from srtstudio.project import Project,Segment
        project=Project(source=self.editor.project.video,duration=self.editor.info['duration']/1000,
            segments=[Segment(s.start/1000,s.end/1000,s.text,s.original or s.text,review=True) for s in track.segments])
        self._send_transcript(project)

    def capture_session(self):
        if self.transcription:
            if (self.editor.project.transcript is None and not self.transcription.project.source
                    and not self.transcription.project.segments and not self.transcription.dirty):
                return
            data = json.loads(self.transcription.project.dumps())
            if self.editor.project.transcript != data:
                self.editor.project.transcript = data
                self.editor.dirty = True
                self.editor.update_title()

    def session_saved(self):
        if self.transcription:
            self.transcription.dirty = False
            self.transcription.autosave_path().unlink(missing_ok=True)

    def reset_transcript(self):
        if not self.transcription:
            return
        from srtstudio.project import Project
        speech = self.transcription
        speech.project = Project()
        speech.project_path = None; speech.audio_metadata = None; speech.pending_source = None
        speech.reset_history(); speech.render(); speech.set_audio_source()
        speech.autosave_path().unlink(missing_ok=True)

    def restore_session(self):
        data = self.editor.project.transcript
        if data is None:
            self.reset_transcript()
            return
        from srtstudio.project import Project
        speech = self.speech()
        speech.project = Project.loads(json.dumps(data))
        speech.project_path = None; speech.audio_metadata = None
        speech.reset_history(); speech.render(); speech.set_audio_source()
        self.tabs.setCurrentIndex(0)

    def closeEvent(self, event):
        # Check both projects before stopping either workspace or deleting recovery.
        if hasattr(self,'ai_dialog') and self.ai_dialog.process:
            if not getattr(self,'_closing_ai',False):
                self._closing_ai=True
                self.ai_dialog.process.finished.connect(self.ai_stopped)
            self.ai_dialog.cancel_job()
            event.ignore()
            return
        if self.queue and self.queue.active:
            if not getattr(self,'_closing_queue',False):
                if QMessageBox.question(self,'Kolejka / Queue','Zatrzymać eksport i zamknąć? / Stop export and close?')!=QMessageBox.StandardButton.Yes:
                    event.ignore();return
                self._closing_queue=True
                self.queue.changed.connect(self.queue_stopped)
                self.queue.pause()
            event.ignore();return
        if self.editor.export_process:
            self.editor.error('Zakończ lub anuluj eksport / Finish or cancel the export.')
            event.ignore()
            return
        speech = self.transcription
        if speech and speech.job.active:
            if QMessageBox.question(self, 'Szept', speech.t('stop_close')) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if not self.editor.confirm_unsaved():
            event.ignore()
            return
        if speech and speech.job.active:
            speech.cancel_job()
        if self.queue:
            self.queue.pause();self.queue.release()
        for widget in (self.editor, speech):
            if widget:
                widget.dirty = False
                widget.close()
        event.accept()

    def queue_stopped(self):
        if self._closing_queue and not self.queue.active:
            from PySide6.QtCore import QTimer
            self._closing_queue=False;QTimer.singleShot(0,self.close)

    def ai_stopped(self,*args):
        from PySide6.QtCore import QTimer
        self._closing_ai=False;QTimer.singleShot(0,self.close)
