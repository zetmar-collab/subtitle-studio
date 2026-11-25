"""Opt-in local AI connection and progress, without editing client settings."""
import json
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QFileDialog, QPlainTextEdit, QTableWidget, QTableWidgetItem,
                              QMessageBox)


class AutomationDialog(QDialog):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.controller = workspace.automation
        self.setWindowTitle('Sterowanie AI · MCP / AI control · MCP')
        self.resize(820,620)
        layout = QVBoxLayout(self)
        note = QLabel('Udostępnij folder projektu agentowi AI. Agent może zmieniać otwarty projekt i tworzyć pliki w tym folderze. '
                      'Połączenie jest lokalne i wyłączone, dopóki go nie uruchomisz.\n'
                      'Share a project folder with your AI agent. It can edit this project and create files in that folder. '
                      'The connection is local and disabled until you start it.')
        note.setWordWrap(True); layout.addWidget(note)
        row = QHBoxLayout(); layout.addLayout(row)
        start = QPushButton('Wybierz folder i włącz / Choose folder and enable')
        start.clicked.connect(self.start); row.addWidget(start)
        stop = QPushButton('Wyłącz połączenie / Disable connection')
        stop.clicked.connect(self.stop); row.addWidget(stop)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.config = QPlainTextEdit(); self.config.setReadOnly(True); layout.addWidget(self.config)
        copy = QPushButton('Kopiuj konfigurację MCP / Copy MCP configuration')
        copy.clicked.connect(self.copy); layout.addWidget(copy)
        self.table = QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(['Zadanie / Job','Stan / State','%','Plik / File'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table)
        cancel = QPushButton('Anuluj wybrane zadanie / Cancel selected job')
        cancel.clicked.connect(self.cancel); layout.addWidget(cancel)
        layout.addWidget(QLabel('Dziennik poleceń AI / AI command log'))
        self.log = QTableWidget(0,4)
        self.log.setHorizontalHeaderLabels(['Czas / Time','Polecenie / Command','Wynik / Result','Argumenty / Arguments'])
        self.log.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.log)
        row = QHBoxLayout(); layout.addLayout(row)
        self.revert = QPushButton('Cofnij do stanu sprzed AI / Revert to the state before AI')
        self.revert.setToolTip('Przywraca projekt sprzed pierwszej zmiany AI w tym połączeniu. Można to cofnąć (Ctrl+Z). '
                               '/ Restores the project from before the first AI edit in this connection. Undo with Ctrl+Z.')
        self.revert.clicked.connect(self.restore); row.addWidget(self.revert)
        clear = QPushButton('Wyczyść dziennik / Clear log')
        clear.clicked.connect(lambda: (self.controller.history.clear(), self.refresh_log())); row.addWidget(clear)
        self.controller.logged.connect(self.refresh_log)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
        self.refresh(); self.refresh_log()

    def refresh_log(self):
        entries = list(self.controller.history)[::-1]
        self.log.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            result = 'OK' if entry['ok'] else 'Błąd / Error: '+entry['error']
            for col, content in enumerate((entry['time'], entry['command'], result, entry['arguments'])):
                item = QTableWidgetItem(content); item.setToolTip(content)
                self.log.setItem(row, col, item)
        self.revert.setEnabled(self.controller.baseline is not None)

    def restore(self):
        answer = QMessageBox.question(self, 'MCP', 'Przywrócić projekt sprzed zmian AI? Można to cofnąć (Ctrl+Z).\n'
                                      'Restore the project from before the AI edits? You can undo this (Ctrl+Z).')
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.restore_baseline()
        except ValueError as error:
            QMessageBox.warning(self, 'MCP', str(error))
        self.refresh_log()

    def command(self):
        if getattr(sys,'frozen',False):
            return str(Path(sys.executable).with_name('SubtitleStudio-MCP.exe')), []
        return sys.executable, [str(Path(__file__).resolve().parents[1]/'main.py'),'--mcp']

    def refresh(self):
        controller = self.controller
        text = 'Wyłączone / Disabled'
        config = ''
        if controller.endpoint:
            text = str(controller.root)+'\n'+controller.endpoint
            command, args = self.command()
            args += ['--connect',controller.endpoint]
            config = json.dumps({'mcpServers':{'subtitle-studio':{'command':command,'args':args}}},indent=2,ensure_ascii=False)
            config += '\n\nCodex CLI:\n'+subprocess.list2cmdline(['codex','mcp','add','subtitle-studio','--',command,*args])
            config += '\n\nClaude Code:\n'+subprocess.list2cmdline(['claude','mcp','add','--transport','stdio','subtitle-studio','--',command,*args])
        self.status.setText(text)
        if self.config.toPlainText()!=config:
            self.config.setPlainText(config)
        jobs = list(controller.jobs.values())
        self.table.setRowCount(len(jobs))
        for row,job in enumerate(jobs):
            value = controller.job_public(job)
            for col,content in enumerate((value['kind'],value['state'],str(value['percent']),value['target'] or value['error'])):
                item = QTableWidgetItem(content); item.setToolTip(value['error'])
                self.table.setItem(row,col,item)

    def start(self):
        folder = QFileDialog.getExistingDirectory(self,'Folder projektu / Project folder')
        if folder:
            try:
                self.controller.start(folder); self.refresh()
            except Exception as error:
                QMessageBox.warning(self,'MCP',str(error))

    def stop(self):
        self.controller.stop(); self.refresh()

    def copy(self):
        from PySide6.QtWidgets import QApplication
        command,args = self.command()
        if self.controller.endpoint:
            args += ['--connect',self.controller.endpoint]
            QApplication.clipboard().setText(json.dumps({'mcpServers':{'subtitle-studio':{'command':command,'args':args}}},indent=2))

    def cancel(self):
        jobs = list(self.controller.jobs)
        row = self.table.currentRow()
        if 0<=row<len(jobs):
            self.controller.tool_cancel(jobs[row]); self.refresh()
