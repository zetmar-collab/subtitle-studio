from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QTableWidget,QTableWidgetItem,
                              QComboBox,QPushButton,QLineEdit,QFileDialog,QMessageBox,QDoubleSpinBox)
from core.export.queue import ExportQueue


class ExportQueueDialog(QDialog):
    def __init__(self,workspace):
        super().__init__(workspace);self.workspace=workspace;self.editor=workspace.editor
        from ui.help import install_help
        install_help(self, self.editor)
        path=self.editor.store/'export-queues'/(self.editor.recovery.path.stem+'.exports.json')
        if workspace.queue is None:workspace.queue=ExportQueue(workspace,path)
        self.queue=workspace.queue;self.setWindowTitle('Kolejka eksportów / Export queue');self.resize(1050,750)
        if not getattr(self.queue, '_playback_connected', False):
            from ui.playback import offer_playback
            self.queue.completed.connect(lambda target: offer_playback(self.workspace, target, self.editor.tr_text))
            self.queue._playback_connected = True
        layout=QVBoxLayout(self);layout.addWidget(QLabel('Każde zadanie zachowuje migawkę projektu. / Each job retains its project snapshot.'))
        form=QFormLayout();self.folder=QLineEdit();self.base=QLineEdit('film')
        choose=QPushButton('Folder wyników / Output folder');choose.clicked.connect(self.choose_folder)
        bar=QHBoxLayout();bar.addWidget(self.folder);bar.addWidget(choose);form.addRow(bar)
        form.addRow('Nazwa bazowa / Base name',self.base)
        self.codec=QComboBox();self.codec.addItems(['MP4 H.264','MP4 H.265','WebM VP9']);form.addRow('Format',self.codec)
        self.fps=QDoubleSpinBox();self.fps.setRange(1,120);self.fps.setValue(min(120,self.editor.info['fps']));form.addRow('FPS',self.fps)
        layout.addLayout(form)
        self.variants=QTableWidget(5,6);self.variants.setHorizontalHeaderLabels(['Wariant / Variant','Szer. / Width','Wys. / Height','Kadr / Frame','X napisów / Caption X','Y napisów / Caption Y'])
        for row,(label,width,height) in enumerate([('16:9',1920,1080),('9:16',1080,1920),('1:1',1080,1080),('4:5',1080,1350),('4:3',1440,1080)]):
            item=QTableWidgetItem(label);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if row==0 else Qt.CheckState.Unchecked);self.variants.setItem(row,0,item)
            for col,value in ((1,width),(2,height),(4,self.editor.track().style.x),(5,self.editor.track().style.y)):
                self.variants.setItem(row,col,QTableWidgetItem(str(value)))
            mode=QComboBox();mode.addItems(['Dopasuj / Fit','Przytnij / Crop']);self.variants.setCellWidget(row,3,mode)
        self.variants.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.variants)
        add=QPushButton('Dodaj warianty do kolejki / Queue variants');add.clicked.connect(self.add);layout.addWidget(add)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Plik / File','Stan / State','%','Błąd / Error'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        bar=QHBoxLayout();layout.addLayout(bar)
        for text,callback in [('Start',self.queue.start),('Zatrzymaj / Pause',self.queue.pause),
                              ('Ponów błędne / Retry failed',self.queue.retry),('Wczytaj kolejkę / Load queue',self.load)]:
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        self.path_label=QLabel();self.path_label.setWordWrap(True);layout.addWidget(self.path_label)
        self.queue.changed.connect(self.refresh);self.refresh()

    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,self.windowTitle(),self.folder.text())
        if folder:self.folder.setText(folder)

    def add(self):
        try:
            if not self.editor.project.video:raise ValueError('Najpierw otwórz film / Open a video first')
            folder=Path(self.folder.text())
            if not self.folder.text() or not folder.is_dir():raise ValueError('Wybierz folder wyników / Choose output folder')
            base=self.base.text().strip()
            if not base or any(char in base for char in '\\/:*?"<>|'):raise ValueError('Nieprawidłowa nazwa / Invalid base name')
            suffix='.webm' if self.codec.currentIndex()==2 else '.mp4';targets=[];options=[]
            for row in range(self.variants.rowCount()):
                if self.variants.item(row,0).checkState()!=Qt.CheckState.Checked:continue
                width=int(self.variants.item(row,1).text());height=int(self.variants.item(row,2).text())
                x=float(self.variants.item(row,4).text());y=float(self.variants.item(row,5).text())
                if not 2<=width<=7680 or not 2<=height<=7680 or width%2 or height%2 or not 0<=x<=100 or not 0<=y<=100:
                    raise ValueError('Sprawdź wymiary i pozycję napisów / Check dimensions and caption position')
                targets.append(str(folder/f'{base}-{width}x{height}{suffix}'))
                options.append(dict(width=width,height=height,fps=self.fps.value(),crf=20,
                    codec=['libx264','libx265','libvpx-vp9'][self.codec.currentIndex()],fit='fit' if self.variants.cellWidget(row,3).currentIndex()==0 else 'crop',
                    x=x,y=y,active_track=self.editor.active_track))
            if not targets:raise ValueError('Zaznacz wariant / Select at least one variant')
            existing=[target for target in targets if Path(target).exists()]
            if existing and QMessageBox.question(self,'Nadpisanie / Overwrite','\n'.join(existing)+'\nNadpisać / Overwrite?')!=QMessageBox.StandardButton.Yes:return
            self.workspace.capture_session();self.queue.add(self.editor.project,targets,options)
        except (ValueError,OSError) as error:self.editor.error(error)

    def load(self):
        path,_=QFileDialog.getOpenFileName(self,self.windowTitle(),str(self.queue.path.parent),'Export queue (*.exports.json)')
        if path:
            try:self.queue.load(path)
            except (ValueError,OSError,KeyError,TypeError) as error:self.editor.error(error)

    def refresh(self):
        self.table.setRowCount(len(self.queue.jobs))
        for row,job in enumerate(self.queue.jobs):
            for col,value in enumerate([job['target'],job['state'],str(job['percent']),job['error']]):
                self.table.setItem(row,col,QTableWidgetItem(value))
        self.path_label.setText('Plik wznowienia / Resume file: '+str(self.queue.path))
