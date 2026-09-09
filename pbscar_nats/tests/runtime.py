"""Isolated image-build checks. Runs only with disposable /data."""
import json, os, signal, socket, subprocess, tempfile, time
from pathlib import Path

token='release-test-'+'a'*32+'"\\quoted'
Path('/data').mkdir(exist_ok=True)
log=tempfile.TemporaryFile()
def start(options):
    Path('/data/options.json').write_text(json.dumps(options))
    return subprocess.Popen(['/run.sh'],stdout=log,stderr=log)
def stop(p):
    if p.poll() is None: p.send_signal(signal.SIGTERM)
    p.wait(timeout=10)
def connect(auth):
    sock=socket.create_connection(('127.0.0.1',4222),2)
    sock.settimeout(3); stream=sock.makefile('rb')
    assert stream.readline().startswith(b'INFO ')
    sock.sendall(b'CONNECT '+json.dumps({'auth_token':auth}).encode()+b'\r\nPING\r\n')
    while True:
        line=stream.readline()
        if line==b'PONG\r\n': return sock,stream
        if line.startswith(b'-ERR') or not line:
            stream.close();sock.close();raise PermissionError('rejected')
def request(subject,payload):
    sock,stream=connect(token)
    body=json.dumps(payload).encode()
    sock.sendall(b'SUB _INBOX.release 1\r\nPUB '+subject.encode()+b' _INBOX.release '+str(len(body)).encode()+b'\r\n'+body+b'\r\n')
    try:
        while True:
            line=stream.readline()
            if line.startswith(b'MSG '):
                data=stream.read(int(line.split()[-1]));stream.read(2)
                result=json.loads(data);assert 'error' not in result,result
                return result
            if line==b'PING\r\n': sock.sendall(b'PONG\r\n')
            assert line and not line.startswith(b'-ERR'),line
    finally: stream.close();sock.close()
def wait_ready(p):
    for _ in range(60):
        assert p.poll() is None,'server exited'
        try:
            s,f=connect(token);f.close();s.close();return
        except OSError: time.sleep(.1)
    raise AssertionError('server not ready')

for bad in ('','short',None,17,'x'*1025):
    p=start({'token':bad,'restore_mode':False})
    assert p.wait(timeout=5)!=0
for bad in ('true', 1, None, {}):
    p=start({'token':token,'restore_mode':bad})
    assert p.wait(timeout=5)!=0
p=start({'token':token,'restore_mode':False})
try:
    wait_ready(p)
    uid=next(x for x in Path(f'/proc/{p.pid}/status').read_text().splitlines() if x.startswith('Uid:'))
    assert uid.split()[1]=='10001',uid
    assert Path('/data/server.conf').stat().st_mode & 0o777 == 0o600
    assert Path('/data/jetstream').stat().st_mode & 0o777 == 0o700
    try: connect('wrong-token')
    except PermissionError: pass
    else: raise AssertionError('invalid token accepted')
    request('$JS.API.STREAM.CREATE.RELEASE_TEST',{'name':'RELEASE_TEST','subjects':['release.test'],'storage':'file'})
    request('release.test',{'test':'persist'})
    assert request('$JS.API.STREAM.INFO.RELEASE_TEST',{})['state']['messages']==1
finally: stop(p)
p=start({'token':token,'restore_mode':False})
try:
    wait_ready(p)
    assert request('$JS.API.STREAM.INFO.RELEASE_TEST',{})['state']['messages']==1
finally: stop(p)
log.seek(0); assert token.encode() not in log.read()
print('PASS: invalid options/auth rejected; escaped token works; non-root runtime; JetStream persists; credential absent from logs')
Path('/test-passed').write_text('NATS isolated runtime checks passed\n')
