"""HA-ingress-only NATS configuration and process supervisor."""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import ssl
import subprocess
import threading
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = Path('/data')
SSL = Path('/ssl')
WEB = Path('/opt/nats-console/web')
LOCK = threading.RLock()
BROKER = None
STOP = threading.Event()
CURRENT = None
FAILED = threading.Event()
DEFAULTS = dict(auth_mode='token', token='', users=[], tls=False,
                cert_file='fullchain.pem', key_file='privkey.pem', client_ca='',
                verify_clients=False, file_gb=5, memory_mb=64,
                max_connections=1024, max_payload_kb=1024)


class Invalid(ValueError):
    pass


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' [INFO] ' + message, flush=True)


def ssl_file(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name):
        raise Invalid('Certificate files must be filenames inside the HA /ssl folder.')
    path = SSL / name
    if not path.is_file() or not path.resolve().is_relative_to(SSL.resolve()):
        raise Invalid('A selected certificate file is missing from the HA /ssl folder.')
    return path


def subjects(value):
    if not isinstance(value, list) or len(value) > 128:
        raise Invalid('Use at most 128 subjects per permission list.')
    for subject in value:
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise Invalid('Permission subjects must be nonempty strings.')
        parts = subject.split('.')
        if any(not p or any(c.isspace() or ord(c) < 33 for c in p) for p in parts):
            raise Invalid('Permission subjects cannot contain spaces or empty segments.')
        if any(('*' in p and p != '*') or ('>' in p and (p != '>' or i != len(parts)-1)) for i, p in enumerate(parts)):
            raise Invalid('Use * for one segment and > only as the final segment.')
    return value


def validate(value, old=None):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise Invalid('Unknown configuration fields.')
    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(copy.deepcopy(value))
    if cfg['auth_mode'] not in ('token', 'users'):
        raise Invalid('Choose shared token or individual users.')
    for key in ('tls', 'verify_clients'):
        if type(cfg[key]) is not bool:
            raise Invalid('Encryption switches must be true or false.')
    for key, low, high in [('file_gb', 1, 1024), ('memory_mb', 16, 4096),
                           ('max_connections', 1, 65536), ('max_payload_kb', 1, 8192)]:
        if type(cfg[key]) is not int or not low <= cfg[key] <= high:
            raise Invalid(f'{key}: use a whole number from {low} to {high}.')
    if cfg['token'] == '' and old:
        cfg['token'] = old.get('token', '')
    if not isinstance(cfg['token'], str) or len(cfg['token']) > 1024:
        raise Invalid('Invalid shared token.')
    if cfg['auth_mode'] == 'token' and len(cfg['token']) < 32:
        raise Invalid('Set a shared token of 32–1024 characters.')
    if not isinstance(cfg['users'], list) or len(cfg['users']) > 64:
        raise Invalid('Use at most 64 users.')
    names = set()
    prior = {u['name']: u for u in (old or {}).get('users', [])}
    for user in cfg['users']:
        if not isinstance(user, dict) or set(user) != {'name', 'password', 'publish', 'subscribe'}:
            raise Invalid('Each user needs a name, password and two permission lists.')
        name = user['name']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', name) or name in names:
            raise Invalid('Usernames must be unique and use letters, numbers, dots, underscores or hyphens.')
        names.add(name)
        if user['password'] == '' and name in prior:
            user['password'] = prior[name]['password']
        if not isinstance(user['password'], str) or not 16 <= len(user['password']) <= 1024:
            raise Invalid('Each user needs a password of 16–1024 characters. Blank keeps an existing password.')
        subjects(user['publish'])
        subjects(user['subscribe'])
    if cfg['auth_mode'] == 'users' and not cfg['users']:
        raise Invalid('Add at least one user before selecting individual-user access.')
    if cfg['verify_clients'] and not cfg['tls']:
        raise Invalid('Client certificates require encryption.')
    if cfg['tls']:
        cert, key = ssl_file(cfg['cert_file']), ssl_file(cfg['key_file'])
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            context.load_cert_chain(cert, key)
            subprocess.run(['openssl', 'x509', '-checkend', '0', '-noout', '-in', str(cert)], check=True, capture_output=True)
            if cfg['verify_clients']:
                context.load_verify_locations(ssl_file(cfg['client_ca']))
        except (ssl.SSLError, OSError, subprocess.CalledProcessError) as exc:
            raise Invalid('Certificate/key validation failed. Check the pair, expiry and client CA.') from exc
    return cfg


def bootstrap():
    options = json.loads((DATA / 'options.json').read_text())
    restore = options.get('restore_mode', False)
    if type(restore) is not bool:
        raise Invalid('Snapshot restore mode must be true or false.')
    if (DATA / 'console.json').exists():
        cfg = validate(json.loads((DATA / 'console.json').read_text()))
    else:
        cfg = validate(dict(token=options.get('token', '')))
    return cfg, restore


def render(cfg, restore=False):
    auth = {'token': cfg['token']} if cfg['auth_mode'] == 'token' else {
        'users': [dict(user=u['name'], password=u['password'], permissions={
            'publish': {'allow': u['publish']} if u['publish'] else {'deny': ['>']},
            'subscribe': {'allow': u['subscribe']} if u['subscribe'] else {'deny': ['>']}}) for u in cfg['users']]}
    result = dict(server_name='nats', listen='0.0.0.0:4222', authorization=auth,
                  jetstream=dict(store_dir='/data/jetstream', max_file_store=(cfg['file_gb'] * (2 if restore else 1)) * 1024**3,
                                 max_mem_store=cfg['memory_mb'] * 1024**2),
                  max_connections=cfg['max_connections'], max_payload=cfg['max_payload_kb'] * 1024,
                  debug=False, trace=False)
    if cfg['tls']:
        result['tls'] = dict(cert_file='/data/tls/cert.pem', key_file='/data/tls/key.pem', min_version='1.2')
        if cfg['verify_clients']:
            result['tls'].update(ca_file='/data/tls/ca.pem', verify=True)
    return result


def atomic_file(path, content, broker_readable=False):
    # The parent directory is root-owned: a compromised broker cannot plant links.
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.config-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            if broker_readable:
                os.fchown(stream.fileno(), 10001, 10001)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare_tls(cfg):
    if not cfg['tls']:
        return
    folder = DATA / 'tls'
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chown(folder, 0, 10001)
    folder.chmod(0o750)
    for setting, filename in [('cert_file', 'cert.pem'), ('key_file', 'key.pem'), ('client_ca', 'ca.pem')]:
        if setting == 'client_ca' and not cfg['verify_clients']:
            continue
        path = folder / filename
        atomic_file(path, ssl_file(cfg[setting]).read_bytes(), broker_readable=True)


def write_config(cfg):
    restore = json.loads((DATA / 'options.json').read_text()).get('restore_mode', False)
    if type(restore) is not bool:
        raise Invalid('Snapshot restore mode must be true or false.')
    prepare_tls(cfg)
    path = DATA / 'server.conf'
    atomic_file(path, json.dumps(render(cfg, restore)).encode(), broker_readable=True)
    check = subprocess.run(['nats-server', '-t', '-c', str(path)], capture_output=True)
    if check.returncode:
        raise Invalid('NATS rejected the generated configuration; no settings were saved.')


def start_broker():
    global BROKER
    BROKER = subprocess.Popen(['su-exec', 'natsapp', 'nats-server', '-c', '/data/server.conf'])
    time.sleep(0.3)
    if BROKER.poll() is not None:
        raise Invalid('NATS could not start with these settings.')


def stop_broker():
    if BROKER is not None and BROKER.poll() is None:
        BROKER.terminate()
        try:
            BROKER.wait(timeout=15)
        except subprocess.TimeoutExpired:
            BROKER.kill()
            BROKER.wait(timeout=5)


def deployed_files():
    """Capture the exact running configuration, independent of renewed /ssl files."""
    paths = [DATA / 'server.conf', *(DATA / 'tls' / name for name in ('cert.pem', 'key.pem', 'ca.pem'))]
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def restore_files(snapshot):
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            atomic_file(path, content, broker_readable=True)


def console_users():
    # Only HA's administrator-controlled options can grant console access.
    # Re-read the runtime file; Supervisor refreshes it when the app restarts.
    try:
        users = json.loads((DATA / 'options.json').read_text()).get('console_admin_user_ids', [])
        if not isinstance(users, list) or len(users) > 64 or any(
            not isinstance(user, str) or not re.fullmatch(r'[0-9a-f]{32}', user) for user in users
        ):
            return ()
        return tuple(users)
    except (OSError, ValueError, AttributeError):
        return ()


def apply(value):
    global CURRENT
    with LOCK:
        new = validate(value, CURRENT)
        snapshot = deployed_files()
        try:
            write_config(new)
        except Exception:
            restore_files(snapshot)
            raise
        try:
            stop_broker()
            start_broker()
            atomic_file(DATA / 'console.json', json.dumps(new).encode())
            CURRENT = new
        except Exception:
            log('Apply failed. Attempting to restore the previous broker configuration.')
            stop_broker()
            restore_files(snapshot)
            start_broker()
            raise
        log('Configuration applied. Broker restarted; clients may reconnect.')


def public_state():
    with LOCK:
        cfg = copy.deepcopy(CURRENT)
        token_saved = bool(cfg.pop('token'))
        cfg['token'] = ''
        for user in cfg['users']:
            user['password'] = ''
        files = sorted(p.name for p in SSL.glob('*') if p.is_file() and p.suffix in ('.pem', '.crt', '.key') and p.resolve().is_relative_to(SSL.resolve())) if SSL.exists() else []
        return dict(config=cfg, token_saved=token_saved, certificate_files=files,
                    broker_running=BROKER is not None and BROKER.poll() is None,
                    capabilities=dict(tls=True, users=True, subject_permissions=True, clusters=False, websockets=False),
                    tls_active=cfg['tls'], restart_required=True)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def ingress_peer(self):
        # Check the actual TCP peer, never caller-controlled forwarded headers.
        try:
            peer = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return peer == ipaddress.ip_address('172.30.32.2') and self.headers.get('Sec-Fetch-Site') != 'cross-site'

    def allowed(self):
        # Supervisor removes spoofed identity headers and supplies the session ID.
        # panel_admin only hides the sidebar item; it is not authorization.
        identities = self.headers.get_all('X-Remote-User-Id', [])
        return self.ingress_peer() and len(identities) == 1 and identities[0] in console_users()

    def respond(self, code, content, mime='application/json'):
        body = content if isinstance(content, bytes) else json.dumps(content).encode()
        self.send_response(code)
        for key, val in {'Content-Type': mime, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
                         'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
                         'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'"}.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.ingress_peer():
            self.respond(403, {'error': 'Open this page through Home Assistant ingress.'})
            return
        if self.path == '/api/state':
            if not self.allowed():
                self.respond(403, {'error': 'Console access is not enabled for your HA identity. Ask an HA administrator to add your user ID to Console administrators in the app Configuration, save and restart the app, then refresh.'})
                return
            self.respond(200, public_state())
        elif self.path in ('/', '/app.js', '/style.css'):
            name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[self.path]
            mime = {'/': 'text/html; charset=utf-8', '/app.js': 'text/javascript; charset=utf-8', '/style.css': 'text/css; charset=utf-8'}[self.path]
            self.respond(200, (WEB / name).read_bytes(), mime)
        else:
            self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.allowed() or self.headers.get('X-NATS-Config') != '1':
            self.respond(403, {'error': 'Request not permitted.'})
            return
        if self.path != '/api/config':
            self.respond(404, {'error': 'Not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072 or self.headers.get('Content-Type') != 'application/json':
                raise Invalid('Send a JSON configuration no larger than 128 KiB.')
            apply(json.loads(self.rfile.read(length)))
            self.respond(200, public_state())
        except (Invalid, ValueError, TypeError) as error:
            # Validation errors contain field guidance only, never supplied values.
            self.respond(400, {'error': str(error) if isinstance(error, Invalid) else 'Invalid JSON configuration.'})
        except Exception:
            self.respond(500, {'error': 'Could not apply settings. Check the app log; previous settings were retained where possible.'})


def main():
    global CURRENT
    os.umask(0o077)
    DATA.mkdir(exist_ok=True)
    (DATA / 'jetstream').mkdir(mode=0o700, exist_ok=True)
    subprocess.run(['chown', '-R', 'natsapp:natsapp', str(DATA / 'jetstream')], check=True)
    # Broker can traverse /data but cannot read the root-owned console settings.
    os.chown(DATA, 0, 10001)
    DATA.chmod(0o750)
    httpd = ThreadingHTTPServer(('0.0.0.0', 8099), Handler)
    def shutdown(*_):
        STOP.set()
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    def monitor():
        while not STOP.wait(1):
            with LOCK:
                if BROKER.poll() is not None:
                    FAILED.set()
                    log('NATS exited unexpectedly. Stopping the app for Supervisor recovery.')
                    shutdown()
    try:
        CURRENT, _ = bootstrap()
        write_config(CURRENT)
        start_broker()
        threading.Thread(target=monitor, daemon=True).start()
        log('NATS is running. Open Web UI for encryption, access and storage settings.')
        if not STOP.is_set():
            httpd.serve_forever()
    finally:
        stop_broker()
        httpd.server_close()
    if FAILED.is_set():
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except Invalid as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
