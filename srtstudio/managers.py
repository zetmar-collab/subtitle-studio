import json
import re
import shutil
from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QAbstractItemView, QTabWidget, QWidget, QLineEdit,
                               QPlainTextEdit)

from .engine import MODELS, model_ready
from .jobs import Job
from .paths import data_dir
from .dictionaries import PACKS, installed, archive_pairs, language_code
from .spelling import user_words, save_user_words


class ModelManager(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.t = window, window.t
        self.setWindowTitle(self.t("models"))
        self.resize(940, 670)
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        models_page = QWidget()
        layout = QVBoxLayout(models_page)
        self.tabs.addTab(models_page, self.t("models_tab"))
        self.path = QLabel()
        self.path.setWordWrap(True)
        layout.addWidget(self.path)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([self.t("model"), "MB ↓", "RAM", self.t("installed") + " / MB"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        hint = QLabel(self.t("download_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.buttons = []
        for row in [[("download", self.download), ("cancel", self.cancel), ("remove", self.remove)],
                    [("folder", self.folder), ("locate", self.locate)]]:
            bar = QHBoxLayout()
            for key, callback in row:
                button = QPushButton(self.t(key))
                button.clicked.connect(callback)
                bar.addWidget(button)
                if key != "cancel":
                    self.buttons.append(button)
            layout.addLayout(bar)
        dictionary_page = QWidget()
        dictionary_layout = QVBoxLayout(dictionary_page)
        self.tabs.addTab(dictionary_page, self.t("dictionaries_tab"))
        self.dict_filter = QLineEdit()
        self.dict_filter.setPlaceholderText(self.t("filter_dictionaries"))
        self.dict_filter.textChanged.connect(self.filter_dictionaries)
        dictionary_layout.addWidget(self.dict_filter)
        self.dictionary_table = QTableWidget(0, 3)
        self.dictionary_table.setHorizontalHeaderLabels([self.t("spell"), self.t("dictionary_state"), "MB ↓"])
        self.dictionary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dictionary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.dictionary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        from PySide6.QtWidgets import QHeaderView
        header = self.dictionary_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dictionary_table.currentCellChanged.connect(self.dictionary_selected)
        dictionary_layout.addWidget(self.dictionary_table, 1)
        self.dict_notice = QLabel(self.t("dictionary_notice"))
        self.dict_notice.setWordWrap(True)
        dictionary_layout.addWidget(self.dict_notice)
        bar = QHBoxLayout()
        self.dict_download = QPushButton(self.t("download_dictionary"))
        self.dict_download.clicked.connect(self.download_dictionary)
        self.dict_remove = QPushButton(self.t("remove_dictionary"))
        self.dict_remove.clicked.connect(self.remove_dictionary)
        for button in [self.dict_download, self.dict_remove]:
            bar.addWidget(button)
            self.buttons.append(button)
        for key, callback in [("import_dict", self.import_dictionary), ("user_dictionary", self.edit_user_dictionary)]:
            button = QPushButton(self.t(key))
            button.clicked.connect(callback)
            bar.addWidget(button)
            self.buttons.append(button)
        dictionary_layout.addLayout(bar)
        self.progress = QProgressBar()
        outer.addWidget(self.progress)
        self.status = QLabel()
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        close = QPushButton(self.t("close"))
        close.clicked.connect(self.accept)
        outer.addWidget(close)
        self.job = Job(self)
        self.job.event.connect(self.on_job_event)
        self.job.finished.connect(self.on_job_finished)
        self.refresh()
        self.table.selectRow(2)
        self.refresh_dictionaries()

    def refresh(self):
        root = self.window.model_root()
        self.path.setText(str(root))
        self.table.setRowCount(len(MODELS))
        for i, (name, (_, size, ram)) in enumerate(MODELS.items()):
            p = root / name
            disk = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1_000_000 if p.exists() else 0
            state = f"{self.t('installed')} / {disk:.0f}" if model_ready(p) else self.t("not_installed")
            for col, value in enumerate((name, str(size), ram, state)):
                self.table.setItem(i, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def selected(self):
        row = self.table.currentRow()
        return list(MODELS)[row] if row >= 0 else "small"

    def download(self):
        name = self.selected()
        if (self.window.model_root() / name).exists():
            if model_ready(self.window.model_root() / name):
                self.status.setText(self.t("installed"))
                return
            if QMessageBox.question(self, self.t("model"), self.t("repair_model")) != QMessageBox.StandardButton.Yes:
                return
        self.begin("model", dict(name=name, root=str(self.window.model_root())), self.window.model_root())

    def begin(self, kind, args, root=None):
        if self.job.active:
            return
        self.progress.setRange(0, 0)
        self.status.setText(self.t("download") + "…")
        for b in self.buttons:
            b.setEnabled(False)
        self.kind = kind
        self.job.start(kind, args, root)

    def cancel(self):
        self.job.cancel()

    def on_job_event(self, event):
        if event[0] == "download":
            _, done, total = event
            if total:
                self.progress.setRange(0, 1000)
                self.progress.setValue(int(1000 * done / total))
            self.status.setText(f"{done / 1e6:.1f} / {total / 1e6:.1f} MB" if total else f"{done / 1e6:.1f} MB")
        elif event[0] == "error":
            self.status.setText(self.t("error") + ": " + event[1] + " — " + event[2])
        elif event[0] == "stage":
            self.status.setText(self.t(event[1]))

    def on_job_finished(self, success):
        for b in self.buttons:
            b.setEnabled(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if success else 0)
        if success:
            self.status.setText(self.t("downloaded"))
            if self.kind in {"dictionary", "import_dictionary"}:
                self.window.restart_spelling()
        self.refresh()
        self.refresh_dictionaries()
        self.window.refresh_models()

    def folder(self):
        path = QFileDialog.getExistingDirectory(self, self.t("folder"), str(self.window.model_root()))
        if path:
            self.window.settings.setValue("models", path)
            self.refresh()
            self.window.refresh_models()

    def locate(self):
        path = QFileDialog.getExistingDirectory(self, self.t("locate"))
        if path:
            if model_ready(path):
                self.window.settings.setValue("external_model", path)
                self.window.refresh_models()
                self.window.model.setCurrentIndex(self.window.model.count() - 1)
            else:
                self.status.setText(self.t("invalid_model"))

    def remove(self):
        p = self.window.model_root() / self.selected()
        if p.exists() and QMessageBox.question(self, self.t("remove"), self.t("delete_confirm")) == QMessageBox.StandardButton.Yes:
            # Exact catalog child only; never delete external model directories.
            if p.resolve().parent != self.window.model_root().resolve() or p.is_symlink():
                return
            try:
                shutil.rmtree(p)
                self.refresh()
            except OSError as e:
                self.window.error(e)

    def download_dictionary(self):
        code = self.selected_dictionary()
        if code not in PACKS or self.dictionary_table.isRowHidden(self.dictionary_table.currentRow()):
            return
        if code in installed(data_dir()) and QMessageBox.question(self, self.t("download_dictionary"), self.t("replace_dictionary")) != QMessageBox.StandardButton.Yes:
            return
        self.begin("dictionary", dict(root=str(data_dir()), code=code))

    def selected_dictionary(self):
        row = self.dictionary_table.currentRow()
        return self.dict_codes[row] if 0 <= row < len(self.dict_codes) else "pl"

    def refresh_dictionaries(self):
        selected = self.selected_dictionary() if hasattr(self, "dict_codes") else "pl"
        present = installed(data_dir())
        self.dict_codes = list(PACKS) + sorted(present - set(PACKS))
        self.dictionary_table.setRowCount(len(self.dict_codes))
        for row, code in enumerate(self.dict_codes):
            state = self.t("installed") if code in present else self.t("builtin") if code == "en" else self.t("not_installed")
            mb = sum(f["size"] for f in PACKS[code]["files"]) / 1e6 if code in PACKS else 0
            for col, value in enumerate([self.window.dictionary_name(code), state, f"{mb:.1f}" if mb else "—"]):
                self.dictionary_table.setItem(row, col, QTableWidgetItem(value))
        self.dictionary_table.resizeColumnsToContents()
        self.dictionary_table.selectRow(self.dict_codes.index(selected) if selected in self.dict_codes else 0)
        self.filter_dictionaries(self.dict_filter.text())
        self.dictionary_selected()

    def filter_dictionaries(self, text):
        first = None
        for row in range(self.dictionary_table.rowCount()):
            item = self.dictionary_table.item(row, 0)
            visible = bool(item) and text.casefold() in item.text().casefold()
            self.dictionary_table.setRowHidden(row, not visible)
            if visible and first is None:
                first = row
        if first is not None and self.dictionary_table.isRowHidden(self.dictionary_table.currentRow()):
            self.dictionary_table.selectRow(first)
        self.dictionary_selected()

    def dictionary_selected(self, *args):
        if not hasattr(self, "dict_codes"):
            return
        code = self.selected_dictionary()
        busy = hasattr(self, "job") and self.job.active
        visible = self.dictionary_table.currentRow() >= 0 and not self.dictionary_table.isRowHidden(self.dictionary_table.currentRow())
        self.dict_download.setEnabled(not busy and visible and code in PACKS)
        self.dict_remove.setEnabled(not busy and visible and code in installed(data_dir()))

    def remove_dictionary(self):
        code = self.selected_dictionary()
        folder = data_dir() / "dictionaries" / code
        if code not in installed(data_dir()) or folder.is_symlink() or folder.resolve().parent != (data_dir() / "dictionaries").resolve():
            return
        if QMessageBox.question(self, self.t("remove_dictionary"), self.t("delete_dictionary_confirm").format(code)) != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(folder)
            self.window.restart_spelling()
            self.refresh_dictionaries()
        except OSError as error:
            self.window.error(error)

    def edit_user_dictionary(self):
        code = self.selected_dictionary()
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("user_dictionary") + " · " + code)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.t("user_dictionary_hint")))
        editor = QPlainTextEdit()
        editor.setPlainText("\n".join(sorted(user_words(data_dir(), code))))
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                save_user_words(data_dir(), code, editor.toPlainText().splitlines())
                self.window.custom_words[code] = user_words(data_dir(), code)
                self.window.rehighlight()
            except (OSError, ValueError) as error:
                self.window.error(error)

    def import_dictionary(self):
        aff, _ = QFileDialog.getOpenFileName(self, self.t("import_dict"), "", "Hunspell (*.aff *.zip *.oxt)")
        if not aff:
            return
        args = dict(source=aff, root=str(data_dir()))
        dic = Path(aff).with_suffix(".dic")
        if Path(aff).suffix.lower() in {".zip", ".oxt"}:
            try:
                pairs = archive_pairs(aff)
                if not pairs:
                    raise ValueError(self.t("invalid_dictionary"))
                names = [pair[0] for pair in pairs]
                name, ok = QInputDialog.getItem(self, self.t("import_dict"), self.t("choose_dictionary_pair"), names, 0, False)
                if not ok:
                    return
                args["aff_member"], args["dic_member"] = pairs[names.index(name)]
            except (OSError, ValueError, __import__("zipfile").BadZipFile) as error:
                self.window.error(error)
                return
        elif not dic.exists():
            dicpath, _ = QFileDialog.getOpenFileName(self, self.t("import_dict"), str(Path(aff).parent), "Hunspell (*.dic)")
            if not dicpath:
                return
            dic = Path(dicpath)
        args["dic"] = str(dic)
        code, ok = QInputDialog.getText(self, self.t("spell"), self.t("dict_code"), text=self.selected_dictionary())
        if not ok:
            return
        try:
            args["code"] = language_code(code.strip())
            if args["code"] in installed(data_dir()) and QMessageBox.question(self, self.t("import_dict"), self.t("replace_dictionary")) != QMessageBox.StandardButton.Yes:
                return
            self.begin("import_dictionary", args)
        except (OSError, ValueError) as e:
            self.window.error(e)

    def done(self, result):
        if self.job.active:
            self.job.cancel()
        super().done(result)


def settings_dialog(w):
    if w.job.active:
        w.error(w.t("busy"))
        return
    dialog = QDialog(w)
    dialog.setWindowTitle(w.t("settings"))
    form = QFormLayout(dialog)
    lang = QComboBox()
    lang.addItem("Polski", "pl")
    lang.addItem("English", "en")
    lang.setCurrentIndex(lang.findData(w.ui_language))
    form.addRow(w.t("ui_lang"), lang)
    theme = QComboBox()
    for key in ("system", "light", "dark"):
        theme.addItem(w.t(key), key)
    current_theme = w.workspace.editor.project.theme if hasattr(w, 'workspace') else w.settings.value("theme", "system")
    theme.setCurrentIndex(theme.findData(current_theme))
    form.addRow(w.t("theme"), theme)
    form.addRow(QLabel(w.t("profile")))
    inputs = {}
    for key, label, low, high in [("width", "width", 8, 120), ("lines", "lines_setting", 1, 8),
                                   ("cps", "cps_setting", 1, 100), ("minimum", "min", .1, 20),
                                   ("maximum", "max", .1, 60)]:
        spin = QDoubleSpinBox() if key in ("cps", "minimum", "maximum") else QSpinBox()
        spin.setRange(low, high)
        spin.setValue(getattr(w.project.profile, key))
        inputs[key] = spin
        form.addRow(w.t(label), spin)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        if inputs["minimum"].value() > inputs["maximum"].value():
            w.error(w.t("time"))
            return
        for key, spin in inputs.items():
            setattr(w.project.profile, key, spin.value())
        w.record()
        w.settings.setValue("language", lang.currentData())
        w.settings.setValue("theme", theme.currentData())
        w.ui_language = lang.currentData()
        if hasattr(w, 'workspace'):
            editor = w.workspace.editor
            editor.checkpoint()
            editor.project.language = lang.currentData()
            editor.project.theme = theme.currentData()
            editor.retranslate()
            editor.apply_theme()
        w.apply_theme()
        w.build_ui()
        w.render()
