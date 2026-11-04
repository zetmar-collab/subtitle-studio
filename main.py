import os
import sys


def report_unhandled(kind, value, trace):
    import traceback
    from pathlib import Path
    folder = Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'SubtitleStudio'
    folder.mkdir(parents=True,exist_ok=True)
    # Trace locations help diagnose startup without recording exception values
    # that might contain subtitle text or other imported private data.
    (folder/'startup.log').write_text(kind.__name__+'\n'+''.join(traceback.format_tb(trace)),encoding='utf-8')
    if sys.stderr is not None:
        traceback.print_exception(kind,value,trace)


sys.excepthook = report_unhandled

if __name__ == '__main__':
    if '--render' in sys.argv:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.export.worker import main
        main(sys.argv[2:])
    else:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        from ui.window import Window
        if os.name == 'nt':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('LocalTools.SubtitleStudio')
        app = QApplication(sys.argv)
        from core.fonts import initialize_fonts
        initialize_fonts()
        app.setApplicationName('Subtitle Studio')
        app.setOrganizationName('LocalTools')
        from pathlib import Path
        root = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
        app.setWindowIcon(QIcon(str(root/'assets/icon.ico')))
        window = Window()
        window.show()
        if '--smoke-test' in sys.argv:
            from PySide6.QtCore import QTimer
            from pathlib import Path
            import json
            project, screenshot = sys.argv[2:4]
            window.open_project(project)
            window.player.play()
            QTimer.singleShot(2000,lambda: (window.player.pause(),window.player.setPosition(1700)))
            def capture():
                window.player.pause()
                window.grab().save(screenshot)
                Path(screenshot+'.json').write_text(json.dumps(dict(
                    frame=not window.preview.frame.isNull(),
                    tracks=len(window.project.tracks),logos=len(window.project.logos),
                    wave_samples=len(window.timeline.wave),
                    icon=not window.windowIcon().isNull(),
                    visual_colors=all(not button.icon().isNull() for button in (window.color,window.background,window.outline_color,window.active_color)),
                    media_error=window.player.errorString())))
                window.dirty = False
                app.quit()
            QTimer.singleShot(3500,capture)
        sys.exit(app.exec())
