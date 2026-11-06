import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from .spelling import word_spans, canonical


class SpellHighlighter(QSyntaxHighlighter):
    def __init__(self, editor, window, segment=False):
        super().__init__(editor.document())
        self.editor, self.window, self.segment = editor, window, segment

    def highlightBlock(self, text):
        w = self.window
        index = w.table.currentRow() if self.segment else self.currentBlock().blockNumber()
        language = w.spell_language(index)
        cache = w.spell_cache.get(language, {})
        custom = w.custom_words.get(language, set())
        style = QTextCharFormat()
        style.setUnderlineColor(QColor("#f34b62"))
        style.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        if language == "off":
            return
        for begin, end, word in word_spans(text):
            key = canonical(word).casefold()
            ignored_once = (index, begin, word) in w.ignored_once
            if cache.get(word) is False and key not in custom and (language, key) not in w.ignored and not ignored_once:
                # QTextDocument offsets count UTF-16 code units.
                start = len(text[:begin].encode("utf-16-le")) // 2
                length = len(word.encode("utf-16-le")) // 2
                self.setFormat(start, length, style)


class SpellEdit(QPlainTextEdit):
    def __init__(self, window, segment=False):
        super().__init__()
        self.window, self.segment = window, segment
        self.text_generation = 0
        self.document().contentsChange.connect(self.track_text_change)
        self.setUndoRedoEnabled(False)
        self.setTabChangesFocus(True)
        self.setAcceptDrops(False)
        self.highlighter = SpellHighlighter(self, window, segment)
        self.setMinimumHeight(90)

    def track_text_change(self, position, removed, added):
        if removed or added:
            self.text_generation += 1

    def keyPressEvent(self, event):
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        if event.matches(QKeySequence.StandardKey.Undo):
            self.window.undo()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.window.redo()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.can_edit_selection():
            self.insertPlainText(" ")
            return
        cursor = self.textCursor()
        if not self.segment:
            if cursor.hasSelection():
                allowed = any(event.matches(key) for key in (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.SelectAll, QKeySequence.StandardKey.Find))
                if "\u2029" in cursor.selectedText() and event.key() not in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown) and not allowed:
                    return
            elif (event.key() == Qt.Key.Key_Backspace and cursor.atBlockStart()) or (event.key() == Qt.Key.Key_Delete and cursor.atBlockEnd()):
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if self.can_edit_selection():
            self.insertPlainText(" ".join(source.text().splitlines()))

    def can_edit_selection(self):
        return not self.isReadOnly() and (self.segment or "\u2029" not in self.textCursor().selectedText())

    def cut(self):
        if self.can_edit_selection():
            super().cut()

    def word_cursor(self, position):
        cursor = self.cursorForPosition(position)
        text = cursor.block().text()
        offset = len(text.encode("utf-16-le")[:cursor.positionInBlock() * 2].decode("utf-16-le"))
        for start, end, word in word_spans(text):
            if start <= offset <= end:
                base = cursor.block().position()
                cursor.setPosition(base + len(text[:start].encode("utf-16-le")) // 2)
                cursor.setPosition(base + len(text[:end].encode("utf-16-le")) // 2, QTextCursor.MoveMode.KeepAnchor)
                return cursor, word
        return cursor, ""

    def contextMenuEvent(self, event):
        w = self.window
        selected = self.textCursor()
        clicked = self.cursorForPosition(event.pos())
        if selected.hasSelection() and selected.selectionStart() <= clicked.position() < selected.selectionEnd():
            cursor, word = selected, ""
        else:
            cursor, word = self.word_cursor(event.pos())
        self.setTextCursor(cursor)
        index = w.table.currentRow() if self.segment else cursor.blockNumber()
        language = w.spell_language(index)
        revision = self.text_generation
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        for key, callback in (("undo", w.undo), ("redo", w.redo)):
            menu.addAction(w.t(key), callback)
        menu.addSeparator()
        if word and language != "off" and not self.isReadOnly():
            suggestions = menu.addMenu(w.t("suggestions"))
            cached = w.suggestion_cache.get((language, word))
            if cached is None:
                suggestions.addAction(w.t("checking")).setEnabled(False)
                w.suggestion_menu = (language, word, suggestions, QTextCursor(cursor), revision, self)
                w.request_suggestions(language, word)
            else:
                for replacement in cached:
                    suggestions.addAction(replacement, lambda value=replacement, c=QTextCursor(cursor): w.replace_suggestion(self, c, word, revision, value))
                if not cached:
                    suggestions.addAction(w.t("no_suggestions")).setEnabled(False)
            def ignore_once():
                # For BMP words this equals the Python position; derive it explicitly for Unicode.
                start_utf16 = cursor.selectionStart() - cursor.block().position()
                start = len(cursor.block().text().encode("utf-16-le")[:start_utf16 * 2].decode("utf-16-le"))
                w.ignored_once.add((index, start, word))
                w.rehighlight()
            menu.addAction(w.t("ignore"), ignore_once)
            menu.addAction(w.t("ignore_all"), lambda: w.ignore_word(language, word))
            menu.addAction(w.t("add_word"), lambda: w.add_user_word(language, word))
            menu.addSeparator()
        for label, action in (("copy", self.copy), ("cut", self.cut), ("paste", self.paste)):
            entry = menu.addAction(w.t(label), action)
            if label != "copy":
                entry.setEnabled(self.can_edit_selection())
        menu.exec(event.globalPos())
