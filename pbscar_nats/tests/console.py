"""Security and real NATS TLS/ACL regressions; disposable image-build data only."""
import copy
import importlib.util
import json
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('console', '/opt/nats-console/server.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)
token = 'console-test-' + 'z' * 40
base = console.validate({'token': token})
for patch in ({'tls': 'true'}, {'max_connections': True}, {'file_gb': 0},
              {'max_payload_kb': 9000}, {'auth_mode': 'none'}, {'unknown': 1},
              {'tls': True, 'cert_file': '../options.json'}, {'auth_mode': 'users'}):
    try:
        console.validate({**base, **patch})
    except console.Invalid:
        pass
    else:
        raise AssertionError('invalid configuration accepted')
user = dict(name='reader', password='p' * 32, publish=[], subscribe=['allowed.>'])
cfg = console.validate({**base, 'auth_mode': 'users', 'users': [user]})
masked = copy.deepcopy(cfg)
masked['users'][0]['password'] = ''
assert console.validate(masked, cfg)['users'][0]['password'] == user['password']
for subject in ('a..b', 'a.>.b', 'a*', 'a b', ''):
    try:
        console.subjects([subject])
    except console.Invalid:
        pass
    else:
        raise AssertionError('invalid subject accepted')
console.CURRENT = cfg
state = console.public_state()
assert token not in json.dumps(state) and user['password'] not in json.dumps(state)

Path('/ssl').mkdir(exist_ok=True)
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-keyout', '/ssl/privkey.pem', '-out', '/ssl/fullchain.pem',
                '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
cfg = console.validate({**cfg, 'tls': True})
Path('/data/options.json').write_text(json.dumps({'token': token, 'restore_mode': False}))
Path('/data/console.json').write_text(json.dumps(cfg))
log = tempfile.TemporaryFile()
p = subprocess.Popen(['/run.sh'], stdout=log, stderr=log)

def connect(password='p' * 32, trusted=True, hostname='localhost'):
    sock = socket.create_connection(('127.0.0.1', 4222), 2)
    try:
        # NATS advertises TLS in its initial INFO; all client credentials follow TLS.
        initial = b''
        while not initial.endswith(b'\r\n'):
            initial += sock.recv(1)
        assert json.loads(initial[5:])['tls_required']
        context = ssl.create_default_context(cafile='/ssl/fullchain.pem' if trusted else None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        secure = context.wrap_socket(sock, server_hostname=hostname)
        stream = secure.makefile('rb')
        secure.sendall(b'CONNECT ' + json.dumps({'user': 'reader', 'pass': password}).encode() + b'\r\nPING\r\n')
        while True:
            line = stream.readline()
            if line == b'PONG\r\n':
                return secure, stream
            if not line or line.startswith(b'-ERR'):
                stream.close()
                secure.close()
                raise PermissionError('authentication rejected')
    except Exception:
        sock.close()
        raise

try:
    for _ in range(100):
        assert p.poll() is None, 'TLS broker exited'
        try:
            sock, stream = connect()
            break
        except (ConnectionError, OSError):
            time.sleep(.1)
    else:
        raise AssertionError('TLS broker not ready')
    sock.sendall(b'SUB forbidden.value 1\r\nPING\r\n')
    assert b'Permissions Violation' in stream.readline()
    while stream.readline() != b'PONG\r\n':
        pass
    sock.sendall(b'PUB allowed.value 1\r\nx\r\nPING\r\n')
    assert b'Permissions Violation' in stream.readline(), 'empty publish list must deny'
    stream.close()
    sock.close()
    for arguments in ({'password': 'wrong'}, {'trusted': False}, {'hostname': 'wrong.example'}):
        try:
            sock, stream = connect(**arguments)
        except (ssl.SSLError, PermissionError):
            pass
        else:
            stream.close(); sock.close()
            raise AssertionError('invalid TLS/auth client accepted')
    req = urllib.request.Request('http://127.0.0.1:8099/api/state', headers={'X-Forwarded-For': '172.30.32.2'})
    try:
        urllib.request.urlopen(req, timeout=2)
    except urllib.error.HTTPError as error:
        assert error.code == 403
    else:
        raise AssertionError('direct or spoofed ingress access accepted')
finally:
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=10)
    Path('/data/console.json').unlink(missing_ok=True)
log.seek(0)
logs = log.read()
assert token.encode() not in logs and user['password'].encode() not in logs
print('PASS: TLS trust/hostname and user auth enforced; empty ACL denies; secrets redacted; ingress spoof rejected')
