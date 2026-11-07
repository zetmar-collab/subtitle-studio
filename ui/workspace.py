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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.editor = Window()
        self.editor.brand_bar.hide()
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
        self.setWindowTitle('Subtitle Studio')
        self.resize(1366, 820)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        brand = QLabel('Subtitle Studio')
        brand.setObjectName('brand')
        bar.addWidget(brand)
        self.flow_buttons = []
        for label, callback in [
            ('Rozpoznaj mowę / Recognize speech', self.transcribe_video),
            ('Edytuj tekst / Edit text', self.send_to_transcript),
            ('Zastosuj napisy / Apply captions', self.send_to_editor),
            ('Korekta AI / AI proofreading',self.show_ai),
            ('Krok po kroku / Step by step',self.show_workflow),
        ]:
            button = QPushButton(label)
            self.localize(button, label)
            button.clicked.connect(callback)
            bar.addWidget(button)
            self.flow_buttons.append(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.editor, 'Film i napisy')
        placeholder = QWidget()
        empty = QVBoxLayout(placeholder)
        hint = QLabel()
        hint.setText(self.editor.tr_text('Tutaj rozpoznasz mowę i poprawisz tekst napisów.', 'Recognize speech and review caption text here.'))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(hint)
        self.tabs.addTab(placeholder, 'Rozpoznawanie mowy')
        self.tabs.currentChanged.connect(self.switch_tab)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.editor.windowTitleChanged.connect(self.setWindowTitle)
        project_menu=self.menuBar().addMenu('Projekt')
        self.editor.text(project_menu.menuAction(), 'Projekt', 'Project')
        keys={'Ctrl+N','Ctrl+Shift+O','Ctrl+S','F1','Ctrl+F1','Shift+F1','F11'}
        for action in self.editor.findChildren(QAction):
            if action.shortcut().toString() in keys:action.setShortcut(QKeySequence())
            elif action.shortcut().toString() == 'Ctrl+Shift+S':
                action.setShortcut(QKeySequence('Ctrl+Shift+E'))
        for label,callback,key in [('Nowa sesja / New session',self.editor.new_project,'Ctrl+N'),
                               ('Otwórz sesję / Open session',self.editor.open_project,'Ctrl+Shift+O'),
                               ('Zapisz sesję / Save session',self.editor.save_project,'Ctrl+S'),
                               ('Zapisz sesję jako / Save session as',self.save_as,'Ctrl+Shift+S')]:
            action=project_menu.addAction(label,callback)
            self.localize(action, label)
            if key:action.setShortcut(QKeySequence(key));self.addAction(action)
        tools=self.menuBar().addMenu('Narzędzia')
        self.editor.text(tools.menuAction(), 'Narzędzia', 'Tools')
        for label,callback,key in [('Krok po kroku / Step by step',self.show_workflow,'F4'),
                               ('Pisownia AI · Ollama',self.show_ai,'Ctrl+Shift+A'),
                               ('Napraw synchronizację / Repair timing',self.show_repair,'Ctrl+Shift+H'),
                               ('Słowa na fali audio / Word alignment',self.editor.words_dialog,'Ctrl+Shift+W'),
                               ('Fragmenty do sprawdzenia / Review queue',self.show_review,'Ctrl+Shift+F'),
                               ('Kolejka eksportów / Export queue',self.show_queue,'Ctrl+Shift+Q'),
                               ('Pokaz zdjęć i klipów / Slideshow',self.show_slideshow,'Ctrl+Shift+P')]:
            action = tools.addAction(label,callback)
            self.localize(action, label)
            action.setShortcut(QKeySequence(key))
        for label,callback,key in [
                ('Film i napisy / Video and captions',lambda: self.tabs.setCurrentIndex(0),'F2'),
                ('Rozpoznawanie mowy / Speech recognition',lambda: self.tabs.setCurrentIndex(1),'F3'),
                ('Rozpoznaj mowę / Recognize speech',self.transcribe_video,'F6'),
                ('Sprawdź pisownię / Check spelling',self.check_spelling,'F7'),
                ('Edytuj tekst / Edit text',self.send_to_transcript,'Ctrl+Shift+R'),
                ('Zastosuj napisy / Apply captions',self.send_to_editor,'Ctrl+Shift+G')]:
            action = tools.addAction(label,callback)
            self.localize(action, label)
            action.setShortcut(QKeySequence(key))
        help_menu = self.menuBar().addMenu('Pomoc')
        self.editor.text(help_menu.menuAction(), 'Pomoc', 'Help')
        for pl,en,key,callback in [
                ('Instrukcja obsługi','User guide','F1',self.editor.show_help),
                ('Skróty klawiszowe','Keyboard shortcuts','Ctrl+F1',self.editor.show_shortcuts),
                ('O aplikacji i licencjach','About and licenses','Shift+F1',self.editor.about)]:
            action = help_menu.addAction(self.editor.tr_text(pl,en),callback)
            self.editor.translated.append((action,pl,en))
            action.setShortcut(QKeySequence(key))
        view = self.menuBar().addMenu(self.editor.tr_text('Widok','View'))
        self.editor.translated.append((view.menuAction(),'Widok','View'))
        full_screen = view.addAction(self.editor.tr_text('Pełny ekran','Full screen'),
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        self.editor.translated.append((full_screen,'Pełny ekran','Full screen'))
        full_screen.setShortcut(QKeySequence('F11'))
        self.editor.interfaceChanged.connect(self.sync_interface)
        from PySide6.QtWidgets import QApplication
        QApplication.styleHints().colorSchemeChanged.connect(self.editor.apply_theme)
        self._interface_signature = None
        self.sync_interface()
        self.show_workflow()

    def localize(self, obj, label):
        parts = label.split(' / ', 1)
        self.editor.text(obj, parts[0], parts[-1])

    def check_spelling(self):
        if self.tabs.currentIndex() == 1:
            self.speech().schedule_spell()
        else:
            self.editor.spelling()

    def refresh_actions(self):
        editor = self.editor
        speech = self.transcription
        count = len(speech.project.segments) if speech else 0
        busy = bool(editor.export_process or (speech and speech.job.active))
        ready = [bool(editor.project.video), bool(editor.track().segments), bool(count),
                 bool(editor.track().segments or count), True]
        for index, button in enumerate(self.flow_buttons):
            enabled = ready[index] and (not busy or index == 4)
            button.setEnabled(enabled)
            button.setToolTip('' if enabled else editor.tr_text(
                'Najpierw otwórz film lub dodaj napisy. Jeśli trwa zadanie, poczekaj na jego zakończenie.',
                'Open a video or add captions first. If a task is running, wait for it to finish.'))

    def sync_interface(self):
        from ui.appearance import apply_appearance
        from PySide6.QtWidgets import QApplication
        editor = self.editor
        signature = (editor.project.language, editor.project.theme, editor.interface_font_size(),
                     QApplication.styleHints().colorScheme())
        if signature == getattr(self, '_interface_signature', None):
            return
        self._interface_signature = signature
        apply_appearance(self, editor.project.theme, editor.interface_font_size())
        self.tabs.setTabText(0, editor.tr_text('Film i napisy', 'Video and captions'))
        self.tabs.setTabText(1, editor.tr_text('Rozpoznawanie mowy', 'Speech recognition'))
        self.refresh_actions()
        if self.transcription:
            speech = self.transcription
            if speech.ui_language != editor.project.language:
                speech.ui_language = editor.project.language
                speech.build_ui()
                speech.render()
            speech.apply_theme()
        if self.workflow:
            self.workflow.refresh()

    def speech(self):
        if self.transcription is None:
            from ui.session import IntegratedSpeechWindow
            widget = IntegratedSpeechWindow(self)
            widget.setWindowFlags(Qt.WindowType.Widget)
            self.transcription = widget
            old = self.tabs.widget(1)
            self.tabs.blockSignals(True)
            self.tabs.removeTab(1)
            self.tabs.insertTab(1, widget, self.editor.tr_text('Rozpoznawanie mowy', 'Speech recognition'))
            self.tabs.setCurrentIndex(1)
            self.tabs.blockSignals(False)
            old.deleteLater()
            self.sync_interface()
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
                answer = QMessageBox.question(self, self.editor.tr_text('Źródło napisów', 'Caption source'),
                    self.editor.tr_text('Nagranie transkrypcji różni się od bieżącego filmu.\nDodać napisy do bieżącego filmu bez przesuwania czasów?',
                    'The transcript uses another recording. Add captions to the current video at their original times?'))
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
                answer = QMessageBox.question(self,self.editor.tr_text('Aktualizacja napisów', 'Update captions'),
                    self.editor.tr_text(
                    f'Ścieżka: {linked.name}\nNapisy: {len(old)} → {len(track.segments)}. Zmiany: {changed}\n'
                    'Tak: zaktualizuj tekst i zachowaj wygląd.\nNie: dodaj osobną ścieżkę.\nAnuluj: wróć bez zmian.',
                    f'Track: {linked.name}\nCaptions: {len(old)} → {len(track.segments)}. Changes: {changed}\n'
                    'Yes: update captions and keep the style.\nNo: add a separate track.\nCancel: return without changes.'),
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
