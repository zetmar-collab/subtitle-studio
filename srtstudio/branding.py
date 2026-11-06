"""Shared application identity for Windows shortcuts, taskbar and Qt dialogs."""
import sys

from PySide6.QtGui import QIcon

from .paths import resource_dir

APP_USER_MODEL_ID = "Zetmar.Szept"


def set_process_identity():
    """Call before QApplication so Windows does not group us with Python."""
    if sys.platform != "win32":
        return False
    import ctypes
    function = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    function.argtypes = [ctypes.c_wchar_p]
    function.restype = ctypes.c_long
    return function(APP_USER_MODEL_ID) == 0


def app_icon():
    return QIcon(str(resource_dir() / "assets" / "szept.ico"))
