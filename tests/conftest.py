import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session')
def app():
    instance = QApplication.instance() or QApplication([])
    from core.fonts import initialize_fonts
    initialize_fonts()
    return instance
