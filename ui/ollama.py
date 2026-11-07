import json
import sys
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt,QSettings,QProcess,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,
                              QCheckBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QProgressBar)
from PySide6.QtWidgets import QPlainTextEdit,QHeaderView
from core.ai.ollama import Ollama,local_url
from ui.jobs import Job


class OllamaDialog(QDialog):
    def __init__(self,workspace):
        super().__init__(workspace);self.workspace=workspace;self.process=None;self.temp=None;self.request=0
        from ui.help import install_help
        install_help(self, workspace.editor)
        self.proposals=[];self.context=None;self.closed=False
        self.settings=QSettings('LocalTools','SubtitleStudioAI')
        self.setWindowTitle('Lokalna korekta AI · Ollama');self.resize(1100,680)
        layout=QVBoxLayout(self)
        note=QLabel('Tekst trafia tylko do lokalnej Ollamy. Modele chmurowe są wykluczone. '
            'AI proponuje zmiany — sprawdź je przed zastosowaniem. Nie pobieramy modeli.\n'
            'Local Ollama only; cloud models excluded. Review proposals before applying. No model downloads.')
        note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();self.url=QLineEdit(str(self.settings.value('url','http://127.0.0.1:11434')))
        form.addRow('Lokalny serwer / Local server',self.url)
        self.model=QComboBox();bar=QHBoxLayout();bar.addWidget(self.model)
        self.refresh_button=QPushButton('Odśwież modele / Refresh models');self.refresh_button.clicked.connect(self.refresh_models)
        bar.addWidget(self.refresh_button);form.addRow('Model',bar)
        self.target=QComboBox();self.target.addItems(['Aktywna ścieżka filmu / Video track','Transkrypcja Szept / Transcript'])
        self.target.setCurrentIndex(workspace.tabs.currentIndex());form.addRow('Tekst / Text',self.target)
        self.track_selector=QComboBox();form.addRow('Ścieżka napisów / Caption track',self.track_selector)
        self.selection=QCheckBox('Tylko zaznaczone segmenty / Selected captions only');form.addRow(self.selection)
        self.scope=QLabel();self.scope.setWordWrap(True);form.addRow(self.scope)
        self.input_text=QPlainTextEdit();self.input_text.setReadOnly(True);self.input_text.setMaximumHeight(65)
        form.addRow('Tekst do wysłania / Text to send',self.input_text)
        self.grammar=QCheckBox('Także gramatyka i interpunkcja / Include grammar and punctuation');form.addRow(self.grammar)
        self.thinking=QCheckBox('Dokładniejsza analiza modelu (wolniej) / Model reasoning (slower)')
        self.thinking.setChecked(True);form.addRow(self.thinking)
        self.timeout=QSpinBox();self.timeout.setRange(30,600);self.timeout.setValue(180);self.timeout.setSuffix(' s / partia / batch')
        form.addRow('Limit czasu / Timeout',self.timeout);layout.addLayout(form)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.start=QPushButton('Sprawdź lokalnie przez AI / Check with local AI');self.start.clicked.connect(self.begin);bar.addWidget(self.start)
        self.cancel=QPushButton('Anuluj zadanie / Cancel job');self.cancel.clicked.connect(self.cancel_job);self.cancel.setEnabled(False);bar.addWidget(self.cancel)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Zastosuj / Apply','Nr','Przed / Before','Propozycja / Proposal','Powód / Reason'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0,70);self.table.setColumnWidth(1,45);self.table.setColumnWidth(4,180)
        for column in (2,3):self.table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);layout.addWidget(self.table)
        details=QHBoxLayout();layout.addLayout(details)
        self.before_text=QPlainTextEdit();self.after_text=QPlainTextEdit()
        for label,widget in [('Pełny tekst przed / Full original text',self.before_text),('Pełna propozycja / Full proposal',self.after_text)]:
            widget.setReadOnly(True);widget.setPlaceholderText(label);widget.setMaximumHeight(100);details.addWidget(widget)
        self.table.currentCellChanged.connect(self.details)
        bar=QHBoxLayout();layout.addLayout(bar)
        all_button=QPushButton('Zaznacz wszystko / Select all');all_button.clicked.connect(self.select_all);bar.addWidget(all_button)
        self.apply_button=QPushButton('Zastosuj zaznaczone / Apply checked');self.apply_button.clicked.connect(self.apply);self.apply_button.setEnabled(False);bar.addWidget(self.apply_button)
        self.controls=[self.url,self.model,self.refresh_button,self.target,self.track_selector,self.selection,self.grammar,self.thinking,self.timeout,self.start]
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(250)
        self.target.currentIndexChanged.connect(self.update_scope)
        self.track_selector.currentIndexChanged.connect(self.update_scope)
        self.selection.toggled.connect(self.update_scope)
        self.prepare(workspace.tabs.currentIndex());self.refresh_models()

    def prepare(self, target):
        if self.process:return
        self.track_selector.blockSignals(True);self.track_selector.clear()
        tracks=self.workspace.editor.project.tracks
        for track in tracks:
            self.track_selector.addItem(f'{track.name} · {len(track.segments)} napisów / captions',track.track_id)
        active=min(self.workspace.editor.active_track,len(tracks)-1)
        if not any(segment.text.strip() for segment in tracks[active].segments):
            active=next((i for i,track in enumerate(tracks) if any(segment.text.strip() for segment in track.segments)),active)
        self.track_selector.setCurrentIndex(active);self.track_selector.blockSignals(False)
        self.target.setCurrentIndex(target);self.selection.setChecked(False);self.update_scope()

    def video_track(self):
        track_id=self.track_selector.currentData()
        track=next((track for track in self.workspace.editor.project.tracks if track.track_id==track_id),None)
        if track is None:raise ValueError('Ścieżka została usunięta. Otwórz okno ponownie. / Track removed; reopen this window.')
        return track

    def source(self):
        if self.target.currentIndex()==0:
            owner=self.workspace.editor;track=self.video_track()
            return owner,owner.project,track.segments,owner.selected() if track is owner.track() else []
        owner=self.workspace.speech()
        rows=sorted({item.row() for item in owner.table.selectedIndexes()})
        return owner,owner.project,owner.project.segments,rows

    def update_scope(self):
        if self.process:return
        try:
            owner,project,segments,rows=self.source()
            self.track_selector.setEnabled(self.target.currentIndex()==0)
            self.selection.setEnabled(bool(rows))
            if not rows:self.selection.setChecked(False)
            selected=rows if self.selection.isChecked() else range(len(segments))
            texts=[segments[i].text for i in selected if segments[i].text.strip()]
            self.scope.setText(f'Do sprawdzenia / To check: {len(texts)} napisów / captions · {sum(map(len,texts))} znaków / characters')
            self.input_text.setPlainText('\n\n'.join(texts)[:12000])
        except ValueError as error:
            self.scope.setText(str(error));self.input_text.clear()

    def refresh_models(self):
        if self.process:return
        try:client=Ollama(self.url.text())
        except ValueError as error:self.message.setText(str(error));return
        self.request+=1;token=self.request;self.start.setEnabled(False);self.model.clear()
        self.message.setText('Sprawdzanie lokalnych modeli… / Checking local models…')
        def ready(models):
            if token!=self.request or self.closed:return
            for model in models:self.model.addItem(f"{model['name']} · {model['size']/1e9:.1f} GB",model['name'])
            preferred=str(self.settings.value('model','Gemma4:e2b'))
            self.model.setCurrentIndex(max(0,self.model.findData(preferred)))
            self.start.setEnabled(bool(models))
            self.message.setText(f'Lokalne modele / Local models: {len(models)}' if models else
                'Brak lokalnych modeli tekstowych. Pobierz model w Ollamie, następnie odśwież. / Install a local text model in Ollama, then refresh.')
        def failed(error):
            if token==self.request and not self.closed:self.message.setText(error)
        self.workspace.editor.pool.start(Job(client.models,ready,failed))

    def begin(self):
        if self.process:return
        self.update_scope()
        try:
            url=local_url(self.url.text());model=self.model.currentData()
            if not model:raise ValueError('Wybierz lokalny model / Select a local model')
            owner,project,segments,rows=self.source()
            if hasattr(owner,'job') and owner.job.active:raise ValueError('Zakończ zadanie ASR / Finish the ASR job first')
            selected=rows if self.selection.isChecked() else list(range(len(segments)))
            selected=[i for i in selected if segments[i].text.strip()]
            if not selected:raise ValueError('Brak tekstu / No text to check')
            self.context=(owner,project,segments,{i:(segments[i],segments[i].text,segments[i].start,segments[i].end) for i in selected})
            self.context_target=self.target.currentIndex()
            self.context_track=self.video_track() if self.context_target==0 else None
            captions=[dict(id=i,text=segments[i].text,language=getattr(segments[i],'language',getattr(project,'language','auto'))) for i in selected]
            if any(len(caption['text'])>3000 for caption in captions):raise ValueError('Podziel segmenty dłuższe niż 3000 znaków / Split captions longer than 3000 characters')
            self.temp=tempfile.TemporaryDirectory(prefix='subtitle-ollama-');folder=Path(self.temp.name)
            self.status=folder/'status.json';self.cancel_path=folder/'cancel';config=folder/'job.json'
            config.write_text(json.dumps(dict(url=url,model=model,captions=captions,grammar=self.grammar.isChecked(),thinking=self.thinking.isChecked(),timeout=self.timeout.value()),ensure_ascii=False),encoding='utf-8')
            self.settings.setValue('url',url);self.settings.setValue('model',model)
            self.proposals=[];self.table.setRowCount(0);self.apply_button.setEnabled(False);self.progress.setValue(0)
            for widget in self.controls:widget.setEnabled(False)
            self.cancel.setEnabled(True);self.message.setText(f'Wysyłanie {len(captions)} napisów do {model}… / Sending {len(captions)} captions to {model}…')
            self.process=QProcess(self);self.process.finished.connect(self.finish)
            self.process.errorOccurred.connect(self.process_error)
            args=['--ollama-correct',str(config),str(self.cancel_path),str(self.status)]
            if not getattr(sys,'frozen',False):args.insert(0,str(Path(__file__).resolve().parents[1]/'main.py'))
            self.process.start(sys.executable,args)
        except (ValueError,OSError) as error:self.message.setText(str(error))

    def read_status(self):
        try:return json.loads(self.status.read_text(encoding='utf-8'))
        except (ValueError,OSError,AttributeError):return {}

    def poll(self):
        if self.process:
            status=self.read_status();self.progress.setValue(status.get('percent',self.progress.value()))
            if status.get('stage'):self.message.setText(status['stage'])

    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart and self.process:self.finish(1,None)

    def finish(self,code,status):
        if not self.process:return
        result=self.read_status();cancelled=self.cancel_path.exists()
        self.proposals=result.get('corrections',[]) if code==0 and result.get('done') and not cancelled else []
        self.table.setRowCount(len(self.proposals))
        for row,proposal in enumerate(self.proposals):
            check=QTableWidgetItem();check.setCheckState(Qt.CheckState.Unchecked);self.table.setItem(row,0,check)
            for col,value in enumerate([str(proposal['id']+1),proposal['original'],proposal['text'],proposal['reason']],1):
                self.table.setItem(row,col,QTableWidgetItem(value))
        self.progress.setValue(100 if code==0 and result.get('done') else self.progress.value())
        self.table.resizeRowsToContents()
        if self.proposals:self.table.setCurrentCell(0,2)
        self.message.setText('Anulowano / Cancelled' if cancelled else
            (f'Propozycje / Proposals: {len(self.proposals)}. Sprawdź i zaznacz zmiany. / Review and check changes.'
             if code==0 and result.get('done') else result.get('error','Błąd Ollamy / Ollama failed')))
        for widget in self.controls:widget.setEnabled(True)
        self.cancel.setEnabled(False);self.apply_button.setEnabled(bool(self.proposals))
        self.process.deleteLater();self.process=None;self.temp.cleanup();self.temp=None
        self.update_scope()

    def select_all(self):
        for row in range(self.table.rowCount()):self.table.item(row,0).setCheckState(Qt.CheckState.Checked)

    def details(self,row,*args):
        if 0<=row<len(self.proposals):
            self.before_text.setPlainText(self.proposals[row]['original']);self.after_text.setPlainText(self.proposals[row]['text'])
        else:self.before_text.clear();self.after_text.clear()

    def apply(self):
        try:
            owner,project,segments,originals=self.context
            if (self.target.currentIndex()!=self.context_target or owner.project is not project
                    or (hasattr(owner,'job') and owner.job.active)):
                raise ValueError('Projekt się zmienił. Uruchom sprawdzanie ponownie. / Project changed; check again.')
            proposals=[item for row,item in enumerate(self.proposals) if self.table.item(row,0).checkState()==Qt.CheckState.Checked]
            if not proposals:return
            if owner is self.workspace.editor:
                track=getattr(self,'context_track',owner.track())
                if not any(item is track for item in owner.project.tracks):raise ValueError('Ścieżka się zmieniła / Caption track changed')
                current=track.segments
            else:current=owner.project.segments
            if current is not segments:raise ValueError('Ścieżka się zmieniła / Caption track changed')
            for item in proposals:
                index=item['id'];segment,text,start,end=originals[index]
                if index>=len(current) or current[index] is not segment or (segment.text,segment.start,segment.end)!=(text,start,end):
                    raise ValueError('Tekst lub czasy zmieniły się. Sprawdź ponownie. / Text or timing changed; check again.')
            if owner is self.workspace.editor:owner.checkpoint()
            for item in proposals:
                segment=current[item['id']]
                if not segment.original:segment.original=segment.text
                segment.text=item['text'];segment.words=[];segment.review=True;segment.checked=False
            if owner is self.workspace.editor:owner.refresh()
            else:owner.record();owner.render();owner.autosave()
            self.workspace.capture_session();self.apply_button.setEnabled(False)
            self.update_scope()
            self.message.setText(f'Zastosowano / Applied: {len(proposals)}. Czasy segmentów zachowano; czasy słów wymagają weryfikacji. / Segment timing kept; review word timing.')
        except (ValueError,TypeError,KeyError) as error:self.message.setText(str(error))

    def cancel_job(self):
        if self.process:self.cancel_path.touch();self.process.kill()

    def reject(self):
        self.request+=1;self.closed=True
        if self.process:self.cancel_job()
        super().reject()

    def showEvent(self,event):
        self.closed=False;super().showEvent(event)
