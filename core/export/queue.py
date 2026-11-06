"""Persistent, sequential render jobs; snapshots remain independent of editor changes."""
import json
from pathlib import Path
import sys
import tempfile
from uuid import uuid4
from PySide6.QtCore import QObject,QProcess,QTimer,Signal,QLockFile
from core.projects.model import Project,save
from core.projects.safety import protect_output
from srtstudio.project import atomic_write


class ExportQueue(QObject):
    changed=Signal()

    def __init__(self,parent,path):
        super().__init__(parent)
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=QLockFile(str(self.path)+'.lock')
        if not self.lock.tryLock(0):raise ValueError('Kolejka jest używana / Queue is in use')
        self.jobs=[];self.process=None;self.running=False;self.temp=None;self.current=None
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(250)

    @property
    def active(self):return self.process is not None

    def persist(self):
        atomic_write(self.path,json.dumps(dict(format='subtitle-export-queue',version=1,jobs=self.jobs),ensure_ascii=False,indent=2))

    def add(self,project,targets,options):
        pending=[]
        for target,opts in zip(targets,options,strict=True):
            protect_output(project,target)
            if Path(target).suffix.lower() not in ('.mp4','.mkv','.webm'):
                raise ValueError('Wybierz MP4, MKV lub WebM / Choose MP4, MKV or WebM')
            if any(Path(job['target']).resolve()==Path(target).resolve() for job in self.jobs+pending
                   if job['state'] in ('queued','running')):
                raise ValueError('Powtórzony cel kolejki / Duplicate queue target')
            snapshot=Project.from_data(project.data())
            active=int(opts.get('active_track',0))
            for key in ('x','y'):
                if key in opts:snapshot.tracks[active].style.__setattr__(key,opts[key])
            Project.from_data(snapshot.data())
            pending.append(dict(job_id=uuid4().hex,project=snapshot.data(),target=str(Path(target).resolve()),
                                options=opts,state='queued',percent=0,error=''))
        if len(self.jobs)+len(pending)>200:raise ValueError('Limit 200 zadań / Limit: 200 jobs')
        self.jobs.extend(pending);self.persist();self.changed.emit()

    def load(self,path):
        if self.active:raise ValueError('Najpierw zatrzymaj zadanie / Stop the active job first')
        source=Path(path).resolve()
        if source.stat().st_size>40_000_000:raise ValueError('Kolejka jest zbyt duża / Queue is too large')
        data=json.loads(source.read_text(encoding='utf-8'))
        if data.get('format')!='subtitle-export-queue' or data.get('version')!=1 or not isinstance(data.get('jobs'),list) or len(data['jobs'])>200:
            raise ValueError('Nieprawidłowy plik kolejki / Invalid queue document')
        for job in data['jobs']:
            project=Project.from_data(job['project']);protect_output(project,job['target'])
            if not isinstance(job['options'],dict) or job['state'] not in ('queued','running','done','error','cancelled'):
                raise ValueError('Nieprawidłowe zadanie / Invalid job')
            if job['state']=='running':job['state']='queued';job['percent']=0
        if source!=self.path.resolve():
            lock=QLockFile(str(source)+'.lock')
            if not lock.tryLock(0):raise ValueError('Ta kolejka jest otwarta w innej sesji / Queue is open in another session')
            self.lock.unlock();self.lock=lock;self.path=source
        self.running=False;self.jobs=data['jobs'];self.persist();self.changed.emit()

    def start(self):
        self.running=True;self.poll()

    def retry(self):
        if self.active:return
        for job in self.jobs:
            if job['state'] in ('error','cancelled'):
                job.update(state='queued',percent=0,error='')
        self.persist();self.start()

    def pause(self):
        self.running=False
        if self.active:self.cancel_path.touch()
        self.persist();self.changed.emit()

    def poll(self):
        if self.process:
            try:
                status=json.loads(self.status.read_text(encoding='utf-8'))
                self.current['percent']=status.get('percent',self.current['percent'])
                self.changed.emit()
            except (ValueError,OSError):pass
            return
        if not self.running:return
        job=next((job for job in self.jobs if job['state']=='queued'),None)
        if job is None:
            self.running=False;self.persist();self.changed.emit();return
        self.current=job
        try:
            project=Project.from_data(job['project'])
            if not Path(project.video).is_file():raise ValueError('Brak filmu źródłowego / Missing source video')
            protect_output(project,job['target'])
            self.temp=tempfile.TemporaryDirectory(prefix='subtitle-queue-')
            folder=Path(self.temp.name);self.status=folder/'status.json';self.cancel_path=folder/'cancel'
            save(project,folder/'project.json');(folder/'options.json').write_text(json.dumps(job['options']),encoding='utf-8')
            job.update(state='running',percent=0,error='');self.persist()
            self.process=QProcess(self)
            self.process.finished.connect(self.finish)
            self.process.errorOccurred.connect(self.process_error)
            args=['--render',str(folder/'project.json'),job['target'],str(folder/'options.json'),str(self.cancel_path),str(self.status)]
            if not getattr(sys,'frozen',False):args.insert(0,str(Path(__file__).resolve().parents[2]/'main.py'))
            self.process.start(sys.executable,args);self.changed.emit()
        except Exception as error:
            job.update(state='error',error=str(error));self.running=False
            if self.temp:self.temp.cleanup();self.temp=None
            self.process=None;self.persist();self.changed.emit()

    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart and self.process:self.finish(1,None)

    def finish(self,code,status):
        if not self.process:return
        try:result=json.loads(self.status.read_text(encoding='utf-8'))
        except (ValueError,OSError):result={}
        cancelled=self.cancel_path.exists()
        success=code==0 and result.get('done')
        self.current.update(state='cancelled' if cancelled else ('done' if success else 'error'),
                            percent=100 if success else self.current['percent'],
                            error='' if success else result.get('error','Render process failed'))
        self.process.deleteLater();self.process=None
        self.temp.cleanup();self.temp=None;self.persist();self.changed.emit()

    def release(self):
        self.timer.stop();self.lock.unlock()
