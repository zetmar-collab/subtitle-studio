import copy
from PySide6.QtCore import Qt,Signal,QRectF,QUrl,QTimer
from PySide6.QtGui import QPainter,QColor,QImage,QPixmap
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QVideoSink
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
                              QDialogButtonBox,QPushButton,QComboBox)
from core.compositor.render import compose,fit_frame


class WordTimeline(QWidget):
    changed=Signal(int,int,int)
    selected=Signal(int)

    def __init__(self,segment,wave,duration):
        super().__init__();self.segment=segment;self.wave=wave;self.duration=duration
        self.words=copy.deepcopy(segment.words);self.drag=None;self.wave_start=0;self.setMinimumHeight(125)

    def x_at(self,time):
        return (time-self.segment.start)/max(1,self.segment.end-self.segment.start)*max(1,self.width()-12)+6

    def time_at(self,x):
        return round(self.segment.start+(x-6)/max(1,self.width()-12)*(self.segment.end-self.segment.start))

    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#151c28'))
        p.setPen(QColor('#518b93'))
        for index,value in enumerate(self.wave):
            time=self.wave_start+index/max(1,len(self.wave))*self.duration
            if self.segment.start<=time<=self.segment.end:
                x=self.x_at(time);p.drawLine(round(x),35-round(value*24),round(x),35+round(value*24))
        for index,word in enumerate(self.words):
            rect=QRectF(self.x_at(word['start']),70,self.x_at(word['end'])-self.x_at(word['start']),30)
            p.fillRect(rect,QColor('#626ac8'));p.setPen(QColor('white'))
            p.drawRect(rect);p.drawText(rect.adjusted(4,0,-2,0),Qt.AlignmentFlag.AlignVCenter,word['text'])
        p.end()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        x=event.position().x()
        for index,word in enumerate(self.words):
            if self.x_at(word['start'])-5<=x<=self.x_at(word['end'])+5:
                self.selected.emit(index)
                self.drag=(index,'start' if abs(x-self.x_at(word['start']))<abs(x-self.x_at(word['end'])) else 'end')
                return

    def mouseMoveEvent(self,event):
        if not self.drag:return
        index,edge=self.drag;word=self.words[index];value=self.time_at(event.position().x())
        low=self.words[index-1]['end'] if index else self.segment.start
        high=self.words[index+1]['start'] if index+1<len(self.words) else self.segment.end
        if edge=='start':word['start']=max(low,min(word['end']-1,value))
        else:word['end']=min(high,max(word['start']+1,value))
        self.changed.emit(index,word['start'],word['end']);self.update()

    def mouseReleaseEvent(self,event):
        self.drag=None


class WordTimingDialog(QDialog):
    def __init__(self,owner,row):
        super().__init__(owner);self.owner=owner;self.row=row;self.loading=False
        self.segment=copy.deepcopy(owner.track().segments[row]);tokens=self.segment.text.split()
        if not tokens or self.segment.end-self.segment.start<len(tokens):
            raise ValueError('Najpierw ustaw tekst i poprawny czas napisu / Set text and valid timing first')
        if len(self.segment.words)!=len(tokens):
            self.segment.words=[dict(text=word,start=self.segment.start+i*(self.segment.end-self.segment.start)//len(tokens),
                                     end=self.segment.start+(i+1)*(self.segment.end-self.segment.start)//len(tokens))
                                for i,word in enumerate(tokens)]
        for word,token in zip(self.segment.words,tokens):word['text']=token
        self.project=copy.deepcopy(owner.project)
        self.project.tracks[owner.active_track].segments[row]=self.segment
        self.project.tracks[owner.active_track].style.effect='highlight'
        self.setWindowTitle('Słowa na fali audio / Word alignment');self.resize(950,750)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Przeciągnij krawędzie słów; kliknij słowo i odsłuchaj. / Drag word edges; select a word and listen.'))
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumHeight(250);layout.addWidget(self.preview)
        self.canvas=WordTimeline(self.segment,owner.timeline.wave,owner.info['duration']);layout.addWidget(self.canvas)
        self.table=QTableWidget(len(tokens),3);self.table.setHorizontalHeaderLabels(['Słowo / Word','Start ms','Koniec / End ms'])
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        self.message=QLabel();layout.addWidget(self.message)
        bar=QHBoxLayout();layout.addLayout(bar)
        play=QPushButton('Odsłuch słowa / Listen to word');play.clicked.connect(self.listen);bar.addWidget(play)
        self.speed=QComboBox()
        for rate in (.5,.75,1):self.speed.addItem(f'{rate}×',rate)
        self.speed.setCurrentIndex(1);bar.addWidget(self.speed)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio)
        self.sink=QVideoSink(self);self.player.setVideoSink(self.sink);self.frame=owner.preview.frame
        self.sink.videoFrameChanged.connect(self.frame_changed);self.player.positionChanged.connect(self.position)
        self.player.errorOccurred.connect(lambda *args:self.message.setText(self.player.errorString()))
        source=owner.project.video or owner.track().source
        if source:self.player.setSource(QUrl.fromLocalFile(source))
        self.stop_at=None;self.canvas.changed.connect(self.dragged);self.canvas.selected.connect(self.table.selectRow)
        self.table.itemChanged.connect(self.edited);self.refresh();self.table.selectRow(0);self.position(self.segment.start)
        self.finished.connect(lambda:self.player.stop())
        if source and not self.canvas.wave:
            import threading
            from ui.jobs import Job,waveform
            stopped=threading.Event();self.finished.connect(lambda:stopped.set())
            def ready(wave):
                if not stopped.is_set():
                    self.canvas.wave=wave;self.canvas.wave_start=self.segment.start
                    self.canvas.duration=self.segment.end-self.segment.start;self.canvas.update()
            owner.pool.start(Job(lambda:waveform(source,cancelled=stopped.is_set,start=self.segment.start/1000,
                duration=(self.segment.end-self.segment.start)/1000),ready,lambda error:None))

    def refresh(self):
        self.loading=True
        for row,word in enumerate(self.segment.words):
            for col,value in enumerate([word['text'],str(word['start']),str(word['end'])]):
                item=QTableWidgetItem(value)
                if col==0:item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row,col,item)
        self.loading=False

    def dragged(self,index,start,end):
        word=self.segment.words[index];word['start']=start;word['end']=end
        word.pop('probability',None);self.segment.review=True;self.segment.checked=False
        self.refresh();self.position(start)

    def edited(self,item):
        if self.loading:return
        try:
            words=[dict(text=self.table.item(i,0).text(),start=int(self.table.item(i,1).text()),
                        end=int(self.table.item(i,2).text())) for i in range(self.table.rowCount())]
            from core.subtitles.transcription import aligned_words
            if not aligned_words(self.segment.text,words,self.segment.start,self.segment.end,'text'):
                raise ValueError('Czasy muszą rosnąć bez nakładania i mieścić się w napisie / Check word boundaries')
            self.segment.words=words;self.canvas.words=copy.deepcopy(words);self.canvas.update()
            self.segment.review=True;self.segment.checked=False;self.message.clear()
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        except ValueError as error:
            self.message.setText(str(error));self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def listen(self):
        row=max(0,self.table.currentRow());word=self.segment.words[row]
        self.stop_at=min(self.segment.end,word['end']+200)
        self.player.setPlaybackRate(self.speed.currentData());self.player.setPosition(max(0,word['start']-200));self.player.play()

    def frame_changed(self,frame):
        if frame.isValid():self.frame=frame.toImage()
        self.position(self.player.position())

    def position(self,ms):
        if self.stop_at is not None and ms>=self.stop_at:
            self.player.pause();self.stop_at=None
        frame=self.frame
        if frame.isNull():
            frame=QImage(640,360,QImage.Format.Format_RGB888);frame.fill(Qt.GlobalColor.black)
        self.preview.setPixmap(QPixmap.fromImage(compose(fit_frame(frame,640,360),self.project,ms)))

    def apply(self):
        self.owner.checkpoint()
        self.owner.track().segments[self.row]=copy.deepcopy(self.segment)
        self.owner.track().style.effect='highlight';self.owner.refresh()
