"""Offline Markdown manual, shared by the editor and the integrated workspace."""
from pathlib import Path
import sys
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QTextCursor, QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser, QLineEdit, QLabel


def install_help(dialog, editor):
    """Dialog shortcuts belong to that window, including when it is modal."""
    for key, callback in [('F1', editor.show_help), ('Ctrl+F1', editor.show_shortcuts)]:
        action = QAction(dialog)
        action.setShortcut(QKeySequence(key))
        action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        action.triggered.connect(lambda checked=False, cb=callback: cb(dialog))
        dialog.addAction(action)


class HelpDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Pomoc — Subtitle Studio')
        self.resize(900, 700)
        self.root = (Path(sys.executable).parent if getattr(sys, 'frozen', False)
                     else Path(__file__).resolve().parents[1]) / 'docs'
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.back = QPushButton('Wstecz')
        self.back.clicked.connect(self.go_back)
        home = QPushButton('Spis treści')
        home.clicked.connect(lambda: self.show_file('POMOC.md'))
        shortcuts = QPushButton('Skróty klawiszowe')
        shortcuts.clicked.connect(lambda: self.show_file('POMOC.md', 'skroty'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Znajdź w otwartym rozdziale…')
        self.search.setAccessibleName('Znajdź w otwartym rozdziale pomocy')
        self.search.returnPressed.connect(self.find_next)
        find_action = QAction(self)
        find_action.setShortcut(QKeySequence('Ctrl+F'))
        find_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find_action.triggered.connect(self.search.setFocus)
        self.addAction(find_action)
        next_button = QPushButton('Znajdź dalej')
        next_button.clicked.connect(self.find_next)
        for widget in (self.back, home, shortcuts, self.search, next_button):
            bar.addWidget(widget)
        layout.addLayout(bar)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.follow_link)
        self.browser.setAccessibleName('Instrukcja obsługi Subtitle Studio')
        layout.addWidget(self.browser)
        self.history = []
        self.current = None
        self.show_file('POMOC.md')

    def show_file(self, name, anchor='', record=True):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root.resolve()) or path.suffix.lower() != '.md':
            return
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            self.message.setText('Brakuje pliku pomocy. Zachowaj folder docs obok programu lub zainstaluj go ponownie.')
            return
        if record and self.current:
            self.history.append((self.current, self.browser.verticalScrollBar().value()))
        self.current = str(path.relative_to(self.root.resolve()))
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent) + '/'))
        self.browser.setMarkdown(text)
        self.message.clear()
        self.back.setEnabled(bool(self.history))
        if anchor:
            self.scroll_to(anchor)

    def scroll_to(self, anchor):
        self.browser.scrollToAnchor(anchor)
        # Qt's Markdown importer may discard an HTML named anchor. Locate the
        # heading as well, so the shortcut command works in packaged Qt builds.
        if anchor == 'skroty':
            cursor = self.browser.document().find('Skróty klawiszowe — wspólne okno programu')
            if not cursor.isNull():
                self.browser.setTextCursor(cursor)
                self.browser.ensureCursorVisible()

    def follow_link(self, url):
        if url.scheme() in ('http', 'https'):
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(url)
        elif not url.scheme() or url.isLocalFile():
            if not url.path():
                self.scroll_to(url.fragment())
                return
            path = Path(url.toLocalFile()) if url.isLocalFile() else Path(self.current).parent / url.path()
            self.show_file(path, url.fragment())

    def go_back(self):
        if self.history:
            name, position = self.history.pop()
            self.show_file(name, record=False)
            self.browser.verticalScrollBar().setValue(position)

    def find_next(self):
        text = self.search.text()
        if not text:
            return
        found = self.browser.find(text)
        if not found:
            self.browser.moveCursor(QTextCursor.MoveOperation.Start)
            found = self.browser.find(text)
        self.message.setText('' if found else 'Nie znaleziono tekstu w tym rozdziale.')
