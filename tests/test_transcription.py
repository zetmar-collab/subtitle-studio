import copy
import time
import pytest
from core.projects.model import Segment, Track
from core.subtitles.transcription import to_track, to_transcript
from srtstudio.project import Project, Segment as SpeechSegment


def transcript():
    return Project(source='recording.wav', duration=3, segments=[
        SpeechSegment(.101, 1.999, 'Dzień dobry.', 'Dzień dobry.',
                      [dict(word=' Dzień', start=.101, end=.8),
                       dict(word=' dobry.', start=.81, end=1.999)])])


def test_exact_units_words_and_roundtrip():
    speech = transcript()
    original = copy.deepcopy(speech)
    track = to_track(speech)
    assert speech == original
    segment = track.segments[0]
    assert (segment.start, segment.end) == (101, 1999)
    assert segment.words == [dict(text='Dzień', start=101, end=800),
                             dict(text='dobry.', start=810, end=1999)]
    restored = to_transcript(track, 'recording.wav', 3000)
    assert restored.segments[0].words[1]['start'] == .81
    assert restored.segments[0].text == speech.segments[0].text
    assert restored.duration == 3


@pytest.mark.parametrize('mutation', ['edited', 'rounding', 'outside', 'overlap', 'multiword'])
def test_stale_or_invalid_word_alignment_is_discarded(mutation):
    speech = transcript()
    segment = speech.segments[0]
    if mutation == 'edited':
        segment.text = 'Zmieniony tekst.'
    elif mutation == 'rounding':
        segment.words[0]['end'] = .1011
    elif mutation == 'outside':
        segment.words[0]['start'] = 0
    elif mutation == 'overlap':
        segment.words[1]['start'] = .7
    else:
        segment.words = [dict(word='Dzień dobry.', start=.101, end=1.999)]
    assert to_track(speech).segments[0].words == []


@pytest.mark.parametrize('kind', ['empty', 'negative', 'overlap', 'beyond'])
def test_invalid_transcript_is_rejected(kind):
    speech = transcript()
    if kind == 'empty':
        speech.segments = []
    elif kind == 'negative':
        speech.segments[0].start = -.1
    elif kind == 'overlap':
        speech.segments.append(SpeechSegment(1, 2, 'Overlap'))
    else:
        speech.duration = 1
    with pytest.raises(ValueError):
        to_track(speech)


def test_reverse_conversion_rejects_untimed_and_invalidates_changed_text():
    with pytest.raises(ValueError):
        to_transcript(Track(segments=[Segment(0, 1, 'Text', timed=False)]))
    track = to_track(transcript())
    track.segments[0].text = 'Nowy tekst'
    converted = to_transcript(track)
    assert converted.segments[0].words == []
    assert converted.segments[0].review


def test_workspace_transfer_undo_close_and_real_probe(app, monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox
    from ui.window import Window
    from srtstudio.ui import Window as SpeechWindow
    import srtstudio.ui as speech_ui
    from ui.workspace import Workspace
    monkeypatch.setenv('SZEPT_DATA_DIR', str(tmp_path/'speech-data'))
    monkeypatch.setattr(Window, 'recover', lambda self: None)
    monkeypatch.setattr(SpeechWindow, 'recover', lambda self: None)
    monkeypatch.setattr(speech_ui, 'QSettings', lambda *args: QSettings(str(tmp_path/'settings.ini'), QSettings.Format.IniFormat))
    settings = QSettings(str(tmp_path/'settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('language', 'pl')
    workspace = Workspace()
    workspace.show()
    errors = []
    monkeypatch.setattr(workspace.editor, 'error', lambda e: errors.append(str(e)))
    speech = workspace.speech()
    monkeypatch.setattr(speech, 'error', lambda e: errors.append(str(e)))
    try:
        assert workspace.tabs.count() == 2
        assert speech.parent() is not None and not speech.isWindow()
        assert all(a.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut for a in speech.shortcut_actions)
        # Use a real application fixture with an audio stream.
        from core.projects.model import load
        source = load('examples/Demo.subtitlelogo.json').video
        from core.media.tools import probe
        workspace.editor.set_video(source, probe(source))
        starts=[]
        monkeypatch.setattr(speech,'start_asr',lambda:starts.append(speech.project.source))
        workspace.transcribe_video()
        deadline = time.monotonic() + 15
        while speech.job.active and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert not speech.job.active
        assert speech.project.duration > 0 and speech.audio_metadata
        assert starts==[source]
        speech.project = transcript()
        speech.project.source = source
        before = copy.deepcopy(workspace.editor.project.data())
        workspace.send_to_editor()
        assert not errors
        assert workspace.editor.track().segments[0].words[1]['start'] == 810
        assert workspace.tabs.currentIndex() == 0
        workspace.editor.undo()
        assert workspace.editor.project.data() == before
        workspace.editor.project.tracks.append(to_track(transcript()))
        workspace.editor.active_track = len(workspace.editor.project.tracks)-1
        monkeypatch.setattr(speech, 'confirm_save', lambda: True)
        workspace.send_to_transcript()
        assert not errors and workspace.tabs.currentIndex() == 1
        assert speech.project.segments[0].words[0]['start'] == .101
        assert speech.autosave_path().name.startswith('transcript-')
        assert workspace.editor.autopath.is_file()
        # Shortcuts belong to the active embedded workspace, including menu actions.
        from PySide6.QtTest import QTest
        speech.project.segments[0].text = 'Tekst po zmianie'
        speech.record()
        speech.render()
        speech.table.setFocus()
        app.processEvents()
        QTest.keyClick(speech.table, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert speech.project.segments[0].text == 'Dzień dobry.'
        monkeypatch.setattr(workspace.editor, 'confirm_unsaved', lambda: False)
        event = QCloseEvent()
        workspace.closeEvent(event)
        assert not event.isAccepted()
        assert speech.poll_timer.isActive() and speech.spell_process.is_alive()
    finally:
        monkeypatch.setattr(workspace.editor, 'confirm_unsaved', lambda: True)
        monkeypatch.setattr(speech, 'confirm_save', lambda: True)
        workspace.close()
        app.processEvents()
    from shiboken6 import isValid
    # Closing the workspace now also releases its Qt children, rather than
    # leaving the hidden window and its timers alive until Python shuts down.
    assert not isValid(speech.poll_timer) or not speech.poll_timer.isActive()
    assert speech.spell_process is None
    assert not speech.autosave_path().exists()
