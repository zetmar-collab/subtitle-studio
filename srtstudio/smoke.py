"""Explicit offline diagnostic mode for testing a frozen package."""
import json
import os
import tempfile
import time
import wave
from pathlib import Path


def offline_asr_worker(args, output):
    import socket
    from .engine import worker
    def deny(*args, **kwargs):
        raise RuntimeError("Network access forbidden during offline ASR test")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    worker("asr", args, output)


def run_dictionaries(root, report_path):
    import sys
    import socket
    from .dictionaries import PACKS, load_dictionary
    from .project import atomic_write
    def deny(*args, **kwargs):
        raise RuntimeError("Network forbidden in dictionary test")
    socket.socket.connect = deny
    socket.create_connection = deny
    words = {"pl": "który", "en": "hello", "en_GB": "colour", "de": "Haus", "de_AT": "Haus", "de_CH": "Haus",
             "fr": "bonjour", "es": "hola", "it": "ciao", "pt_PT": "casa", "pt_BR": "casa", "uk": "книга",
             "ru": "книга", "cs": "kniha", "sk": "kniha", "nl": "boek", "sv": "bok", "da": "bog",
             "nb": "bok", "hu": "könyv", "ro": "carte", "tr": "kitap"}
    suggestions = {"pl": ("ktury", "który"), "en": ("helllo", "hello"), "de": ("Huas", "Haus"),
                   "fr": ("bonjor", "bonjour"), "es": ("holaa", "hola")}
    report = dict(ok=False, frozen=bool(getattr(sys, "frozen", False)), cases=[])
    try:
        for code in PACKS:
            dictionary = load_dictionary(root, code)
            accepted = dictionary.lookup(words[code])
            rejected = not dictionary.lookup("книгааа" if code in {"uk", "ru"} else "qzxvqqzxx")
            result = dict(code=code, accepted=accepted, rejects_typo=rejected)
            if code in suggestions:
                wrong, right = suggestions[code]
                result["suggestions"] = list(dictionary.suggest(wrong))[:6]
                assert right in result["suggestions"], result
            assert accepted and rejected, result
            report["cases"].append(result)
            del dictionary
        report["ok"] = True
    except Exception as error:
        report["error"] = str(error)
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def run_asr(request_path, report_path):
    """Run explicit fixtures through the packaged worker with network denied."""
    import multiprocessing as mp
    import queue
    import sys
    from .audio import probe
    from .project import Project, Segment, atomic_write, export
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    report = dict(ok=False, frozen=bool(getattr(sys, "frozen", False)), cases=[])
    try:
        for case in request["cases"]:
            duration = probe(case["source"])["duration"]
            with tempfile.TemporaryDirectory(prefix="szept-frozen-asr-") as work:
                args = dict(source=case["source"], model=request["model"], duration=duration,
                            language=case.get("language"), device="cpu", work=work)
                ctx = mp.get_context("spawn")
                output = ctx.Queue()
                process = ctx.Process(target=offline_asr_worker, args=(args, output))
                process.start()
                started = time.monotonic()
                segments, detected = [], case.get("language")
                try:
                    while True:
                        if time.monotonic() - started > 180:
                            raise TimeoutError(case["source"])
                        try:
                            event = output.get(timeout=.2)
                        except queue.Empty:
                            if not process.is_alive():
                                raise RuntimeError(f"Worker exit: {process.exitcode}")
                            continue
                        if event[0] == "error":
                            raise RuntimeError(str(event))
                        if event[0] == "segment":
                            segments.append(Segment(**event[1]))
                        if event[0] == "language":
                            detected = event[1]
                        if event[0] == "done":
                            break
                    process.join(timeout=10)
                    if process.exitcode != 0:
                        raise RuntimeError(f"Worker exit: {process.exitcode}")
                finally:
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=5)
                    process.close()
                    output.close()
            project = Project(source=case["source"], duration=duration, language=detected or "auto",
                              model="tiny", segments=segments, original_text=" ".join(s.text for s in segments))
            destination = Path(report_path).parent / (case["name"] + "-frozen")
            for fmt in (["json", "txt", "srt", "vtt"] if segments else ["json"]):
                atomic_write(destination.with_suffix("." + fmt), export(project, fmt))
            report["cases"].append(dict(name=case["name"], language=detected, segments=len(segments),
                words=sum(len(s.words) for s in segments), text=project.original_text,
                duration=duration, seconds=round(time.monotonic() - started, 2), offline_socket_block=True))
        report["ok"] = True
    except Exception as error:
        report["error"] = str(error)
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def run(report_path):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="szept-smoke-") as directory:
        os.environ["SZEPT_DATA_DIR"] = directory
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QSettings
        from .ui import Window
        from .audio import probe, binary
        from .project import Project, Segment
        from .managers import ModelManager
        import ctranslate2
        import faster_whisper
        from .branding import app_icon, set_process_identity
        identity = set_process_identity()
        app = QApplication([])
        app.setWindowIcon(app_icon())
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory)
        w = Window()
        icon_sizes = sorted(size.width() for size in w.windowIcon().availableSizes())
        assert {16, 24, 32, 48, 64, 128, 256}.issubset(icon_sizes), icon_sizes
        w.settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
        audio = Path(directory) / "test ą.wav"
        with wave.open(str(audio), "wb") as f:
            f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            f.writeframes(b"\0" * 32000)
        metadata = probe(audio)
        w.project = Project(duration=1, language="en", segments=[Segment(0, 1, "hello helllo")])
        w.reset_history()
        w.render()
        w.check_spelling()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and w.spell_cache.get("en", {}).get("helllo") is not False:
            app.processEvents()
            time.sleep(.05)
        assert w.spell_cache["en"]["hello"] is True
        assert w.spell_cache["en"]["helllo"] is False
        w.request_suggestions("en", "helllo")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and "hello" not in w.suggestion_cache.get(("en", "helllo"), []):
            app.processEvents()
            time.sleep(.05)
        assert "hello" in w.suggestion_cache[("en", "helllo")]
        from PySide6.QtGui import QTextCursor
        cursor = w.segment_edit.textCursor()
        cursor.setPosition(6)
        cursor.setPosition(12, QTextCursor.MoveMode.KeepAnchor)
        generation = w.segment_edit.text_generation
        w.rehighlight()
        assert w.segment_edit.text_generation == generation
        w.replace_suggestion(w.segment_edit, cursor, "helllo", generation, "hello")
        assert w.project.segments[0].text == "hello hello"
        manager = ModelManager(w)
        manager.show()
        app.processEvents()
        assert manager.table.rowCount() == 5
        assert manager.dictionary_table.rowCount() >= 22
        manager.close()
        from . import __version__
        report = dict(ok=True, app_version=__version__, faster_whisper=faster_whisper.__version__,
                      cpu_compute_types=sorted(ctranslate2.get_supported_compute_types("cpu")),
                      metadata=metadata, ffmpeg=binary("ffmpeg"), ffprobe=binary("ffprobe"),
                      spelling=True, suggestions=True, suggestion_replacement=True, dictionary_catalog=manager.dictionary_table.rowCount(),
                      model_manager=True, icon_sizes=icon_sizes, windows_identity=identity,
                      frozen=bool(__import__("sys").frozen if hasattr(__import__("sys"), "frozen") else False))
        Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        w.dirty = False
        w.close()
    return 0
