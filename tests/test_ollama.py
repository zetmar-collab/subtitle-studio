import json
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
import pytest
from core.ai.ollama import Ollama,local_url


@pytest.fixture
def server():
    state=SimpleNamespace(requests=[],proposals=None,remote=False)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.answer(dict(models=[dict(name='local:test',size=1234),dict(name='x:cloud',size=0),
                                     dict(name='custom-cloud',size=1234),dict(name='nomic-embed-text',size=1234)]))
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state.requests.append((self.path,data))
            if self.path=='/api/show':
                self.answer(dict(capabilities=['completion'],model_info={'general.architecture':'llama'},
                                 remote_host='https://cloud.invalid' if state.remote else None))
            else:
                captions=json.loads(data['prompt'])['captions']
                proposals=state.proposals if state.proposals is not None else [dict(id=c['id'],text=c['text'].replace('ktury','który'),reason='Pisownia') for c in captions if 'ktury' in c['text']]
                self.answer(dict(response=json.dumps(dict(corrections=proposals)),done=True))
        def answer(self,data):
            body=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    state.url=f'http://127.0.0.1:{http.server_port}'
    yield state
    http.shutdown();http.server_close();thread.join()


@pytest.mark.parametrize('url',['https://ollama.com','http://192.168.1.2:11434','http://localhost.attacker.test',
                               'http://user:pass@localhost:11434','http://localhost:11434/path','http://localhost:11434?x=1'])
def test_remote_or_ambiguous_endpoints_are_rejected(url):
    with pytest.raises(ValueError):local_url(url)


def test_local_models_structured_proposals_and_no_download_calls(server):
    client=Ollama(server.url)
    assert [model['name'] for model in client.models()]==['local:test']
    progress=[]
    result=client.correct('local:test',[dict(id=5,text='ktury kolor?',language='pl')],progress=progress.append)
    assert result==[dict(id=5,original='ktury kolor?',text='który kolor?',reason='Pisownia')]
    assert progress[-1]['percent']==100
    paths=[path for path,_ in server.requests];assert paths==['/api/show','/api/generate']
    request=server.requests[-1][1]
    assert request['stream'] is False and request['format']['type']=='object'


def test_cloud_alias_rejected_before_sending_text(server):
    server.remote=True
    with pytest.raises(ValueError):Ollama(server.url).correct('local:test',[dict(id=0,text='private sample')])
    assert [path for path,_ in server.requests]==['/api/show']


@pytest.mark.parametrize('proposal',[[dict(id=999,text='wrong',reason='')],
                                    [dict(id=0,text='',reason='')],
                                    [dict(id=0,text='a',reason=''),dict(id=0,text='b',reason='')]])
def test_invalid_model_proposals_are_rejected(server,proposal):
    server.proposals=proposal
    with pytest.raises(ValueError):Ollama(server.url).correct('local:test',[dict(id=0,text='ktury')])


def test_batched_texts_and_cancel(server):
    captions=[dict(id=i,text='ktury'+' '*400) for i in range(20)]
    result=Ollama(server.url).correct('local:test',captions)
    assert len(result)==20 and len([path for path,_ in server.requests if path=='/api/generate'])>1
    with pytest.raises(InterruptedError):Ollama(server.url).correct('local:test',captions,cancelled=lambda:True)


def test_redirect_never_sends_text_elsewhere():
    from core.ai.ollama import NoRedirect
    with pytest.raises(ValueError):NoRedirect().redirect_request(None,None,None,None,None,'https://example.com')
