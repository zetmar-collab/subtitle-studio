"""User-enabled local IPC. All project operations run on the Qt GUI thread."""
import copy
import json
import math
import re
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QObject, QProcess, QTimer, QEventLoop, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QImage, QFontDatabase
from PySide6.QtWidgets import QApplication
from core.projects.model import Project, Segment, Style, Banner, Logo, save, load
from core.projects.safety import protect_output, source_paths
from core.media.tools import probe, probe_audio


READONLY = {'state','assets','fonts','job','cancel','banner_templates','disconnect'}


class Automation(QObject):
    logged = Signal()

    def __init__(self, workspace):
        super().__init__(workspace)
        self.workspace = workspace
        self.editor = workspace.editor
        self.root = None
        self.endpoint = None
        self.jobs = {}
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept_connections)
        self.buffers = {}
        self.in_call = False
        self.template_path = None  # None: the user's application data folder
        self.history = deque(maxlen=200)
        self.baseline = None

    def log_call(self, request, response):
        arguments = request.get('arguments', {})
        if isinstance(arguments, dict) and isinstance(arguments.get('captions'), list):
            arguments = dict(arguments, captions=f'[{len(arguments["captions"])} captions]')
        summary = json.dumps(arguments, ensure_ascii=False, default=str)
        self.history.append({'time':time.strftime('%H:%M:%S'),'command':str(request.get('command','?')),
                             'arguments':summary if len(summary) <= 300 else summary[:297]+'...',
                             'ok':'error' not in response,'error':response.get('error','')})
        self.logged.emit()

    def remember_baseline(self):
        """Keep the project state from before the first AI edit of this session."""
        if self.baseline is None:
            self.baseline = {'project':self.editor.project.data(),'path':self.editor.path,
                             'video':self.editor.project.video,'info':dict(self.editor.info)}

    def restore_baseline(self):
        """Return to the pre-AI state as one undoable editor step."""
        if self.baseline is None:
            raise ValueError('Brak zmian AI do cofnięcia / No AI changes to revert')
        if self.busy():
            raise ValueError('Najpierw zakończ zadanie / Finish the running job first')
        old_video = self.editor.project.video
        self.editor.checkpoint()
        self.editor.project = Project.from_data(copy.deepcopy(self.baseline['project']))
        self.editor.path = self.baseline['path']
        self.editor.restore_view(old_video)
        self.baseline = None
        self.history.append({'time':time.strftime('%H:%M:%S'),'command':'restore_baseline','arguments':'',
                             'ok':True,'error':''})
        self.logged.emit()

    def background(self, function, *args):
        """Run blocking I/O off the GUI thread while keeping the window responsive."""
        box = {}
        def work():
            try:
                box['value'] = function(*args)
            except BaseException as error:  # re-raised on the GUI thread
                box['error'] = error
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        while thread.is_alive():
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            thread.join(0.01)
        if 'error' in box:
            raise box['error']
        return box['value']

    def start(self, root, endpoint=None):
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Wybierz folder projektu / Choose a project folder')
        if self.busy():
            raise ValueError('Najpierw zakończ zadanie / Finish the running job first')
        self.stop()
        self.root = root
        self.endpoint = endpoint or ('subtitle-studio-' + uuid4().hex)
        if not re.fullmatch(r'subtitle-studio-[a-zA-Z0-9_-]{1,80}', self.endpoint):
            raise ValueError('Invalid IPC endpoint')
        if not self.server.listen(self.endpoint):
            raise ValueError(self.server.errorString())
        self.baseline = None
        return {'endpoint':self.endpoint,'root':str(self.root)}

    def stop(self):
        self.server.close()
        for socket in list(self.buffers):
            socket.abort(); socket.deleteLater()
        self.buffers.clear()
        self.endpoint = None

    def busy(self):
        return (any(job['state']=='running' for job in self.jobs.values()) or self.editor.export_process is not None
                or bool(self.workspace.transcription and self.workspace.transcription.job.active)
                or bool(self.workspace.queue and self.workspace.queue.active))

    def accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if len(self.buffers)>=16:
                socket.abort(); socket.deleteLater(); continue
            self.buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket:self.read(s))
            socket.disconnected.connect(lambda s=socket:self.disconnected(s))
            # The socket is the timer context: Qt drops the call if it is deleted first.
            QTimer.singleShot(30000, socket, socket.abort)

    def disconnected(self, socket):
        self.buffers.pop(socket,None)
        socket.deleteLater()

    def read(self, socket):
        buffer = self.buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer)>2_000_000:
            socket.abort(); return
        if b'\n' not in buffer:
            return
        # One request per connection: drop the buffer before running it so that
        # bytes arriving later can never execute the same command again.
        self.buffers.pop(socket, None)
        socket.readyRead.disconnect()
        try:
            request = json.loads(bytes(buffer).split(b'\n',1)[0])
            if not isinstance(request,dict) or not isinstance(request.get('command'),str):
                self.log_call({'command':'?'}, {'error':'Invalid request'})
                raise ValueError('Invalid request')
            result = self.call(request['command'],request.get('arguments',{}))
            response = {'result':result}
        except Exception as error:
            response = {'error':str(error) or type(error).__name__}
        if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
            socket.write((json.dumps(response,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
            socket.flush(); socket.disconnectFromServer()

    def path(self, value, output=False, overwrite=False):
        if type(overwrite) is not bool:
            raise ValueError('overwrite must be a boolean')
        if not self.root:
            raise ValueError('Automation is disabled')
        path = Path(value)
        path = (self.root/path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Ścieżka poza udostępnionym folderem / Path outside the shared folder')
        if output:
            protect_output(self.editor.project,path)
            if not path.parent.is_dir() or path.is_dir():
                raise ValueError('Output parent folder must exist and target must be a file')
            if path.exists() and not overwrite:
                raise ValueError('Output exists; explicitly set overwrite=true or choose another path')
        elif not path.exists():
            raise ValueError('File or folder does not exist')
        return path

    def assert_sources(self):
        if any(not path.is_relative_to(self.root) for path in source_paths(self.editor.project)):
            raise ValueError('The current project references files outside the shared folder')

    def call(self, command, arguments):
        """Run one command; edits and every failure go to the AI command log
        (read-only polling such as state/job is not logged, so it cannot flood it)."""
        try:
            result = self.dispatch(command, arguments)
        except Exception as error:
            self.log_call({'command':command,'arguments':arguments}, {'error':str(error) or type(error).__name__})
            raise
        if command not in READONLY:
            self.log_call({'command':command,'arguments':arguments}, {'result':True})
        return result

    def dispatch(self, command, arguments):
        if not self.server.isListening():
            raise ValueError('Automation is disabled')
        if not isinstance(arguments,dict):
            raise ValueError('Arguments must be an object')
        method = getattr(self,'tool_'+command,None) if command.isidentifier() else None
        if method is None:
            raise ValueError('Unknown automation command')
        if command not in READONLY:
            # A previous command may still be waiting for FFmpeg in background();
            # only read-only commands may run during that nested event loop.
            if self.in_call or self.busy() or QApplication.activeModalWidget():
                raise ValueError('Finish the running job or close the dialog before editing the project')
            self.remember_baseline()
        previous, self.in_call = self.in_call, True
        try:
            return method(**arguments)
        finally:
            self.in_call = previous

    def tool_state(self):
        self.assert_sources()
        return {'root':str(self.root),'project_path':self.editor.path,'dirty':self.editor.dirty,
                'project':self.editor.project.data(),'media':self.editor.info,
                'jobs':[self.job_public(job) for job in self.jobs.values()]}

    def tool_assets(self, directory='.'):
        path = self.path(directory)
        if not path.is_dir():
            raise ValueError('Expected directory')
        extensions = {'.mp4','.mov','.mkv','.webm','.wav','.mp3','.flac','.m4a','.png','.jpg','.jpeg','.webp','.bmp','.srt','.vtt','.json'}
        files = [str(p.relative_to(self.root)) for p in path.iterdir()
                 if p.is_file() and p.suffix.lower() in extensions and p.resolve().is_relative_to(self.root)]
        return {'files':sorted(files)[:500],'truncated':len(files)>500}

    def tool_fonts(self):
        return {'fonts':QFontDatabase.families()}

    def tool_new_project(self, discard_changes=False):
        if type(discard_changes) is not bool:
            raise ValueError('discard_changes must be a boolean')
        if (self.editor.dirty or (self.workspace.transcription and self.workspace.transcription.dirty)) and not discard_changes:
            raise ValueError('Save the project first or explicitly set discard_changes=true')
        original = self.editor.confirm_unsaved
        self.editor.confirm_unsaved = lambda:True
        try:
            if not self.editor.new_project():
                raise ValueError('Could not create a new project')
        finally:
            self.editor.confirm_unsaved = original
        return self.tool_state()

    def tool_open_project(self, path, discard_changes=False):
        target = self.path(path)
        project = load(target)
        if any(not p.is_relative_to(self.root) for p in source_paths(project)):
            raise ValueError('Project references files outside the shared folder')
        info = self.background(probe, project.video) if project.video else None
        self.tool_new_project(discard_changes)
        self.editor.project = project; self.editor.path = str(target)
        if project.video:
            self.editor.set_video(project.video,info,preserve_range=True)
        self.workspace.restore_session()
        self.editor.history.clear(); self.editor.future.clear(); self.editor._history_sizes={}
        self.editor.dirty = False; self.editor.refresh()
        return self.tool_state()

    def tool_save_project(self, path, overwrite=False):
        target = self.path(path,True,overwrite)
        self.assert_sources(); self.workspace.capture_session()
        save(self.editor.project,target)
        self.editor.path = str(target); self.editor.dirty = False
        self.workspace.session_saved(); self.editor.update_title()
        return {'path':str(target)}

    def tool_open_video(self, path):
        target = self.path(path)
        self.editor.set_video(str(target),self.background(probe, target))
        return self.tool_state()

    def tool_captions(self, captions, name='Napisy AI', track_index=0):
        if not isinstance(captions,list) or len(captions)>10000:
            raise ValueError('Limit: 10000 captions')
        segments = [Segment(**item) for item in captions]
        if any(not 0<=s.start<s.end<=self.editor.info['duration'] for s in segments):
            raise ValueError('Caption times must be inside the video, in milliseconds')
        project = copy.deepcopy(self.editor.project)
        if not 0<=track_index<len(project.tracks):
            raise ValueError('Invalid track index')
        project.tracks[track_index].segments = segments
        project.tracks[track_index].name = name
        Project.from_data(project.data())
        self.editor.checkpoint(); self.editor.project = project
        self.editor.active_track=track_index; self.editor.active_logo=self.editor.active_banner=-1
        self.editor.refresh()
        return {'count':len(segments),'track_index':track_index}

    def tool_style(self, changes, track_index=0):
        project = copy.deepcopy(self.editor.project)
        if type(track_index) is not int or not 0<=track_index<len(project.tracks):
            raise ValueError('Invalid track index')
        style = asdict(project.tracks[track_index].style)
        style.update(changes)
        project.tracks[track_index].style = Style(**style).validate()
        Project.from_data(project.data())
        self.editor.checkpoint(); self.editor.project=project; self.editor.refresh()
        return asdict(project.tracks[track_index].style)

    def tool_banner_templates(self):
        from core.projects import banner_templates
        return {'templates':banner_templates.all_templates(self.template_path)}

    def tool_banner(self, properties, banner_id=None, template=None):
        from core.projects import banner_templates
        if not isinstance(properties,dict):
            raise ValueError('properties must be an object')
        current = next((b for b in self.editor.project.banners if b.banner_id==banner_id),None)
        if banner_id and current is None:
            raise ValueError('Unknown banner id')
        if current is None and len(self.editor.project.banners)>=64:
            raise ValueError('Limit: 64 banners')
        base = current or Banner()
        if template is not None:
            # The template sets the look first; explicit properties still win.
            base = banner_templates.apply(base, template, self.template_path)
        data = asdict(base); data.update(properties)
        data['banner_id'] = current.banner_id if current else Banner().banner_id
        value = Banner(**data).validate()
        self.editor.checkpoint()
        if current:
            index = self.editor.project.banners.index(current)
            self.editor.project.banners[index] = value
        else:
            self.editor.project.banners.append(value); index=len(self.editor.project.banners)-1
        self.editor.active_banner=index; self.editor.active_logo=-1; self.editor.refresh()
        return asdict(value)

    def tool_remove_banner(self, banner_id):
        if not any(b.banner_id==banner_id for b in self.editor.project.banners):
            raise ValueError('Unknown banner id')
        self.editor.checkpoint()
        self.editor.project.banners = [b for b in self.editor.project.banners if b.banner_id!=banner_id]
        self.editor.active_banner=-1; self.editor.refresh()
        return {'removed':banner_id}

    def tool_logo(self, path, x=88, y=12, width=15, opacity=100, start=0, end=2147483647, keyframes=None):
        from core.compositor.render import image
        target = self.path(path)
        image(target)
        project = copy.deepcopy(self.editor.project)
        project.logos.append(Logo(path=str(target),x=x,y=y,width=width,opacity=opacity,start=start,end=end,
                                  keyframes=keyframes if keyframes is not None else []))
        Project.from_data(project.data())
        self.editor.checkpoint(); self.editor.project=project
        self.editor.active_banner=-1; self.editor.active_logo=len(project.logos)-1; self.editor.refresh()
        return {'logo_index':self.editor.active_logo}

    def dimensions(self, width, height, fps):
        if (type(width) is not int or type(height) is not int or width%2 or height%2
                or not 2<=width<=7680 or not 2<=height<=7680
                or type(fps) not in (int,float) or not math.isfinite(fps) or not 1<=fps<=120):
            raise ValueError('Expected even dimensions 2..7680 and FPS 1..120')
        return {'width':width,'height':height,'fps':fps}

    def tool_create_blank_video(self, output, seconds=5, width=1920, height=1080, fps=25,
                               color='#20354b', overwrite=False):
        target = self.path(output,True,overwrite)
        if target.suffix.lower()!='.mp4' or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):
            raise ValueError('Expected MP4 output and #RRGGBB color')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not .1<=seconds<=86400:
            raise ValueError('Duration must be 0.1..86400 seconds')
        return self.start_job('color', {'target':str(target),'color':color,'seconds':seconds,
            'options':self.dimensions(width,height,fps)}, target, auto_open=True)

    def tool_create_video(self, visual, audio, output, width=1920, height=1080, fps=25,
                          fit='fit', overwrite=False):
        visual, audio = self.path(visual),self.path(audio)
        target = self.path(output,True,overwrite)
        if target in (visual,audio) or target.suffix.lower()!='.mp4' or fit not in ('fit','crop'):
            raise ValueError('Choose a new MP4 output and fit/crop')
        options = self.dimensions(width,height,fps); options['fit']=fit
        return self.start_job('create-video',{'visual':str(visual),'audio':str(audio),
            'target':str(target),'options':options},target,auto_open=True)

    def tool_join_videos(self, paths, output, width=1920, height=1080, fps=25, overwrite=False):
        if not isinstance(paths,list) or not 2<=len(paths)<=100:
            raise ValueError('Expected 2..100 video paths')
        sources = [str(self.path(p)) for p in paths]
        target = self.path(output,True,overwrite)
        if str(target) in sources or target.suffix.lower()!='.mp4':
            raise ValueError('Choose a new MP4 output')
        return self.start_job('join',{'paths':sources,'target':str(target),
            'options':self.dimensions(width,height,fps)},target,auto_open=True)

    def tool_slideshow(self, clips, audio, output, width=1920, height=1080, fps=25, overwrite=False):
        if not isinstance(clips,list) or not 1<=len(clips)<=40:
            raise ValueError('Expected 1..40 clips')
        items = [{'path':str(self.path(c['path'])),'seconds':c.get('seconds',3)} for c in clips]
        audio = self.path(audio)
        target = self.path(output,True,overwrite)
        if target==audio or any(str(target)==item['path'] for item in items) or target.suffix.lower()!='.mp4':
            raise ValueError('Choose a new MP4 output')
        options = self.dimensions(width,height,fps)
        options.update(auto_duration=True,fade=True,motion=False)
        return self.start_job('slideshow',{'clips':items,'audio':str(audio),'target':str(target),'options':options},
                              target,auto_open=True)

    def framing(self, fit, crop_x):
        if fit not in ('fit','crop') or type(crop_x) not in (int,float) or not math.isfinite(crop_x) or not 0<=crop_x<=100:
            raise ValueError('fit must be fit/crop and crop_x 0..100')
        return {'fit':fit,'crop_x':crop_x}

    def tool_export_video(self, output, width=1920, height=1080, fps=25, crf=20,
                          codec='libx264', start=0, seconds=None, overwrite=False, fit='fit', crop_x=50):
        self.assert_sources()
        if not self.editor.project.video:
            raise ValueError('Open or create a video first')
        target = self.path(output,True,overwrite)
        if (codec not in ('libx264','libx265','libvpx-vp9') or target.suffix.lower() not in ('.mp4','.mkv','.webm')
                or (codec=='libvpx-vp9') != (target.suffix.lower()=='.webm')
                or type(crf) is not int or not 0<=crf<=51):
            raise ValueError('Invalid codec, output extension or CRF')
        options = self.dimensions(width,height,fps)
        if type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<self.editor.info['duration']/1000:
            raise ValueError('Invalid export start')
        options.update(crf=crf,codec=codec,start=start,**self.framing(fit,crop_x))
        if seconds is not None:
            if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<=0:
                raise ValueError('Invalid duration')
            options['seconds']=seconds
        return self.start_job('render',{'project':self.editor.project.data(),'options':options},target)

    def tool_transcribe(self, model_path, language=None, device='cpu'):
        from srtstudio.engine import model_ready
        self.assert_sources()
        if not self.editor.project.video:
            raise ValueError('Open or create a video first')
        if language is not None and (not isinstance(language,str) or not re.fullmatch(r'[a-z]{2,3}',language)):
            raise ValueError('language must be an ISO code such as pl or en, or null for detection')
        model = self.path(model_path)
        if not model_ready(model) or device not in ('cpu','cuda'):
            raise ValueError('Select a downloaded local Whisper model and cpu/cuda')
        source = self.path(self.editor.project.video)
        duration = self.background(probe_audio, source)['duration']/1000
        return self.start_job('transcribe',{'source':str(source),'model':str(model),'language':language,
            'device':device,'duration':duration,'profile':{}},None)

    def tool_import_captions(self, path):
        from core.subtitles.service import read
        target = self.path(path)
        if target.stat().st_size>20_000_000:
            raise ValueError('Subtitle file exceeds 20 MB')
        return self.tool_captions([asdict(s) for s in read(target)],name=target.stem)

    def tool_export_captions(self, output, track_index=0, overwrite=False):
        from core.subtitles.service import write
        self.assert_sources()
        if type(track_index) is not int or not 0<=track_index<len(self.editor.project.tracks):
            raise ValueError('Invalid track index')
        target = self.path(output,True,overwrite)
        if target.suffix.lower() not in ('.srt','.vtt','.ass'):
            raise ValueError('Choose SRT, VTT or ASS')
        write(self.editor.project.tracks[track_index].segments,target)
        return {'path':str(target)}

    def tool_preview(self, output, time_ms=0, width=960, height=540, overwrite=False, fit='fit', crop_x=50):
        import subprocess
        from core.media.tools import binary, FLAGS
        from core.compositor.render import compose, fit_frame
        self.assert_sources()
        target = self.path(output,True,overwrite)
        if (target.suffix.lower()!='.png' or type(width) is not int or type(height) is not int
                or not 2<=width<=1920 or not 2<=height<=1920):
            raise ValueError('Expected PNG and integer preview dimensions 2..1920')
        if not self.editor.project.video:
            raise ValueError('Open or create a video first')
        if type(time_ms) is not int or not 0<=time_ms<self.editor.info['duration']:
            raise ValueError('Time must be within the video')
        self.framing(fit,crop_x)
        # Decode large enough for both fit and crop, without upscaling a 1920 px preview from 960 px.
        scale = f'scale={width}:{height}:force_original_aspect_ratio={"decrease" if fit=="fit" else "increase"}'
        command = [binary('ffmpeg'),'-v','error','-nostdin','-ss',str(time_ms/1000),
                   '-i',self.editor.project.video,'-frames:v','1','-vf',scale,
                   '-f','image2pipe','-c:v','png','pipe:1']
        result = self.background(lambda: subprocess.run(command,capture_output=True,timeout=30,creationflags=FLAGS))
        frame = QImage.fromData(result.stdout)
        if result.returncode or frame.isNull():
            raise ValueError('Could not decode the requested frame')
        frame = compose(fit_frame(frame,width,height,fit,crop_x),self.editor.project,time_ms)
        if not frame.save(str(target)):
            raise ValueError('Could not save preview')
        self.editor.player.setPosition(time_ms)
        return {'path':str(target),'width':width,'height':height,'time_ms':time_ms}

    def job_public(self, job):
        result = {key:job[key] for key in ('id','kind','state','percent','target','error')}
        if job['state']=='running':
            try:
                result['percent']=json.loads(job['status'].read_text(encoding='utf-8')).get('percent',0)
            except (OSError,ValueError):
                pass
        return result

    def tool_job(self, job_id):
        if job_id not in self.jobs:
            raise ValueError('Unknown job id')
        return self.job_public(self.jobs[job_id])

    def tool_cancel(self, job_id):
        if job_id not in self.jobs:
            raise ValueError('Unknown job id')
        job = self.jobs[job_id]
        if job['state']=='running':
            job['cancel'].touch()
        return self.tool_job(job_id)

    def tool_disconnect(self):
        """Stop listening after this reply; the window and its project stay open."""
        QTimer.singleShot(0, self, self.stop)
        return {'disconnected':True}

    def document_key(self):
        """Identify the open document independently of undo/redo, which replace
        the Project object but keep its path, video and first track id."""
        project = self.editor.project
        return (self.editor.path, project.video, project.tracks[0].track_id if project.tracks else '')

    def start_job(self, kind, data, target, auto_open=False):
        if len(self.jobs)>=64:
            old = next((key for key,job in self.jobs.items() if job['state']!='running'),None)
            if old:
                self.jobs.pop(old)
            else:
                raise ValueError('Too many jobs')
        job_id = uuid4().hex
        temp = tempfile.TemporaryDirectory(prefix='subtitle-automation-')
        folder = Path(temp.name)
        status, cancel = folder/'status.json',folder/'cancel'
        process = QProcess(self)
        job = dict(id=job_id,kind=kind,state='running',percent=0,target=str(target) if target else None,
            error='',process=process,temp=temp,status=status,cancel=cancel,auto_open=auto_open,
            document=self.document_key())
        self.jobs[job_id] = job
        config = folder/'job.json'
        if kind=='render':
            save(self.editor.project,folder/'project.json')
            config.write_text(json.dumps(data['options']),encoding='utf-8')
            args = ['--render',str(folder/'project.json'),str(target),str(config),str(cancel),str(status)]
        else:
            if kind=='transcribe':
                data['target']=str(folder/'transcript.json')
                job['result_file']=Path(data['target'])
            config.write_text(json.dumps(data),encoding='utf-8')
            args = (['--automation-worker',kind] if kind in ('color','transcribe') else ['--'+kind])
            args += [str(config),str(cancel),str(status)]
        if not getattr(sys,'frozen',False):
            args.insert(0,str(Path(__file__).resolve().parents[1]/'main.py'))
        process.finished.connect(lambda code, exit_status,j=job:self.finished(j,code))
        process.errorOccurred.connect(lambda error,j=job:self.finished(j,1)
            if error==QProcess.ProcessError.FailedToStart and j['state']=='running' else None)
        process.start(sys.executable,args)
        self.editor.statusBar().showMessage('AI · '+kind+' — zadanie w tle / background job')
        return self.job_public(job)

    def finished(self, job, code):
        if job['state']!='running':
            return
        try:
            result = json.loads(job['status'].read_text(encoding='utf-8'))
        except (OSError,ValueError):
            result = {}
        success = code==0 and result.get('done')
        job['state']='done' if success else ('cancelled' if job['cancel'].exists() else 'error')
        job['percent']=100 if success else 0
        job['error']='' if success else result.get('error','Worker failed or was cancelled')
        try:
            if success and (job['auto_open'] or job['kind']=='transcribe') and job['document']!=self.document_key():
                # Never apply a result to a different document, but never report it as applied either.
                job['state']='error'
                job['error']=('Projekt w edytorze zmienił się w trakcie zadania; wynik nie został wstawiony. '
                              '/ The open project changed during the job; the result was not applied.'
                              + (f' File: {job["target"]}' if job['target'] else ''))
            elif success:
                if job['auto_open']:
                    self.editor.set_video(job['target'],self.background(probe, job['target']))
                elif job['kind']=='transcribe':
                    from srtstudio.project import Project as SpeechProject, Segment as SpeechSegment
                    from core.subtitles.transcription import to_track
                    segments = json.loads(job['result_file'].read_text(encoding='utf-8'))
                    transcript = SpeechProject(source=self.editor.project.video,
                        duration=self.editor.info['duration']/1000,segments=[SpeechSegment(**s) for s in segments],
                        language=next((s['spell_language'] for s in segments if s.get('spell_language')),'auto'))
                    track = to_track(transcript)
                    speech = self.workspace.speech()
                    speech.project = transcript
                    self.editor.checkpoint(); self.editor.project.tracks.append(track)
                    self.editor.project.linked_track = track.track_id
                    self.editor.active_track=len(self.editor.project.tracks)-1
                    speech.dirty=True; speech.reset_history(); speech.render()
                    self.editor.refresh()
        except Exception as error:
            job['state']='error'; job['error']=str(error)
        job['process'].deleteLater()
        job['temp'].cleanup()
        self.editor.statusBar().showMessage('AI · '+job['kind']+' · '+job['state'],15000)
