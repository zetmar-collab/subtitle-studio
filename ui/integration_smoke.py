"""Explicit diagnostic of both workspaces and their real spawned workers."""
import json
import os
from pathlib import Path
import time
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication


def run(workspace, args):
    args=list(args)
    video_asr='--video-asr' in args
    if video_asr:args.remove('--video-asr')
    ollama_model=None
    if '--ollama-model' in args:
        index=args.index('--ollama-model');ollama_model=args[index+1];del args[index:index+2]
    queue_test='--queue-test' in args
    args=[arg for arg in args if arg!='--queue-test']
    report_path, source = map(Path, args[:2])
    model = Path(args[2]) if len(args) > 2 else None
    report_path.parent.mkdir(parents=True, exist_ok=True)
    root = report_path.parent/'integration-data'
    root.mkdir(exist_ok=True)
    os.environ['SZEPT_DATA_DIR'] = str(root)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from srtstudio import ui
    ui.QSettings = lambda *a: QSettings(str(root/'settings.ini'), QSettings.Format.IniFormat)
    ui.Window.recover = lambda self: None
    settings = ui.QSettings()
    settings.setValue('language', 'pl')
    settings.setValue('theme', 'dark')
    speech = workspace.speech()
    speech.confirm_save = lambda: True
    errors = []
    speech.error = lambda error: errors.append(str(error))
    workspace.editor.error = lambda error: errors.append(str(error))
    from srtstudio.project import Project, Segment
    report = dict(ok=False, frozen=bool(__import__('sys').frozen) if hasattr(__import__('sys'),'frozen') else False)
    state = {'stage':'probe', 'started':time.monotonic()}
    if video_asr:
        assert model is not None
        from core.media.tools import probe
        workspace.editor.set_video(str(source.resolve()),probe(source))
        speech.model.addItem('Local test model', str(model.resolve()))
        speech.model.setCurrentIndex(speech.model.count()-1)
        speech.language.setCurrentIndex(speech.language.findData('pl'));speech.device.setCurrentIndex(0)
        speech.spell.setCurrentIndex(speech.spell.findData('en'))
        workspace.transcribe_video();state['stage']='asr'
    else:
        speech.load_audio(str(source.resolve()))
    timer = QTimer(workspace)
    timer.setInterval(70)

    def finish(error=None):
        timer.stop()
        if error:
            report['error'] = str(error)
        if errors:
            report['worker_errors'] = errors
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        speech.dirty = workspace.editor.dirty = False
        workspace.close()
        QApplication.instance().exit(0 if report['ok'] else 1)

    def poll():
        try:
            if errors:
                raise RuntimeError('; '.join(errors))
            if time.monotonic()-state['started'] > 150:
                raise TimeoutError(state['stage'])
            if speech.job.active:
                return
            if state['stage'] == 'probe':
                assert speech.audio_metadata and speech.project.duration > 0
                report['audio_probe'] = True
                # Test Hunspell through the same worker used by the GUI.
                speech.spell.setCurrentIndex(speech.spell.findData('en'))
                if model:
                    speech.model.addItem('Local test model', str(model.resolve()))
                    speech.model.setCurrentIndex(speech.model.count()-1)
                    speech.language.setCurrentIndex(speech.language.findData('pl'))
                    speech.device.setCurrentIndex(0)
                    speech.start_asr()
                    state['stage'] = 'asr'
                    return
                speech.project.segments = [Segment(.1, .9, 'hello world', 'hello world',
                    [dict(word=' hello', start=.1, end=.4),dict(word=' world',start=.5,end=.9)])]
                state['stage'] = 'asr'
            if state['stage'] == 'asr':
                assert speech.project.segments and not speech.project.incomplete
                if video_asr:
                    assert speech.audio_metadata and speech.project.duration>0
                    report['audio_probe']=True;report['video_button_asr']=True
                if model:
                    report['asr_segments'] = len(speech.project.segments)
                    report['asr_words'] = sum(len(s.words) for s in speech.project.segments)
                    assert report['asr_words'] > 0
                speech.render()
                workspace.send_to_editor()
                assert workspace.tabs.currentIndex() == 0
                track = workspace.editor.track()
                assert track.segments and any(s.words for s in track.segments)
                report['word_timing_transfer'] = True
                from core.projects.model import save, load
                saved = root/'integrated.subtitlelogo.json'
                save(workspace.editor.project, saved)
                assert load(saved).tracks[-1].segments == track.segments
                report['project_roundtrip'] = True
                workspace.editor.grab().save(str(report_path.with_suffix('.video.png')))
                workspace.send_to_transcript()
                assert workspace.tabs.currentIndex() == 1
                assert speech.project.source == str(source.resolve())
                for segment in speech.project.segments:
                    segment.spell_language = 'en'
                speech.spell_errors.clear()
                report['reverse_transfer'] = True
                state['stage'] = 'spelling'
            if state['stage'] == 'spelling':
                # GUI async worker: wait for at least one completed spelling request.
                speech.check_spelling()
                speech.poll_spell()
                if not speech.spell_cache:
                    return
                assert not speech.spell_failed and not speech.spell_errors
                report['native_spelling_worker'] = True
                workspace.grab().save(str(report_path.with_suffix('.png')))
                if queue_test:
                    from core.media.tools import probe
                    from core.export.queue import ExportQueue
                    workspace.editor.set_video(str(source.resolve()),probe(source))
                    workspace.capture_session()
                    workspace.queue=ExportQueue(workspace,root/'smoke.exports.json')
                    workspace.queue.add(workspace.editor.project,[root/'wide.mp4',root/'portrait.mp4'],
                        [dict(width=96,height=64,fps=12,seconds=.5,codec='libx264'),
                         dict(width=64,height=96,fps=12,seconds=.5,codec='libx264',fit='crop')])
                    workspace.queue.start();state['stage']='queue'
                    return
                if ollama_model:
                    start_ai();return
                report['ok'] = True
                finish()
            if state['stage']=='queue':
                if workspace.queue.active or workspace.queue.running:return
                assert all(job['state']=='done' for job in workspace.queue.jobs)
                report['queue_worker']=True
                if ollama_model:
                    start_ai();return
                report['ok']=True;finish()
            if state['stage']=='ai-models':
                dialog=workspace.ai_dialog
                index=dialog.model.findData(ollama_model)
                if index<0:return
                dialog.model.setCurrentIndex(index)
                assert not dialog.selection.isChecked()
                assert 'napewno' in dialog.input_text.toPlainText()
                dialog.begin();assert dialog.process is not None,dialog.message.text()
                state['stage']='ai-result';return
            if state['stage']=='ai-result':
                dialog=workspace.ai_dialog
                if dialog.process:return
                assert len(dialog.proposals)==2,dialog.message.text()
                dialog.select_all();dialog.apply()
                assert speech.project.segments[0].text=='Który kolor wybrać?'
                assert speech.project.segments[1].text=='To na pewno dobry pomysł.'
                assert speech.project.segments[1].start==1
                report['ollama_gui_worker']=True;report['ollama_model']=ollama_model
                report['ollama_captions_sent']=2
                dialog.grab().save(str(report_path.with_suffix('.ollama.png')))
                dialog.reject();report['ok']=True;finish()
        except Exception as error:
            finish(error)
    def start_ai():
        import ui.ollama as ai_ui
        ai_ui.QSettings=lambda *args:QSettings(str(root/'ai.ini'),QSettings.Format.IniFormat)
        speech.project.segments=[Segment(.1,.9,'Ktury kolor wybrać?'),Segment(1,2,'To napewno dobry pomysł.')]
        speech.render();workspace.tabs.setCurrentIndex(1);workspace.show_ai()
        state['stage']='ai-models'

    timer.timeout.connect(poll)
    timer.start()
    workspace._integration_timer = timer
