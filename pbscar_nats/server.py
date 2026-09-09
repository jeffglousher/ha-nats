"""Validate HA startup options and supervise an unprivileged NATS server."""
import copy
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

DATA = Path('/data')
SSL = Path('/ssl')
BROKER = None
STOP = threading.Event()
DEFAULTS = dict(auth_mode='token', token='', users=[], tls=False,
                cert_file='fullchain.pem', key_file='privkey.pem', client_ca='',
                verify_clients=False, file_gb=5, memory_mb=64,
                max_connections=1024, max_payload_kb=1024, provision_nui=True)


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


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise Invalid('Unknown configuration fields.')
    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(copy.deepcopy(value))
    if cfg['auth_mode'] not in ('token', 'users'):
        raise Invalid('Choose shared token or individual users.')
    for key in ('tls', 'verify_clients', 'provision_nui'):
        if type(cfg[key]) is not bool:
            raise Invalid('Encryption switches must be true or false.')
    for key, low, high in [('file_gb', 1, 1024), ('memory_mb', 16, 4096),
                           ('max_connections', 1, 65536), ('max_payload_kb', 1, 8192)]:
        if type(cfg[key]) is not int or not low <= cfg[key] <= high:
            raise Invalid(f'{key}: use a whole number from {low} to {high}.')
    if not isinstance(cfg['token'], str) or len(cfg['token']) > 1024:
        raise Invalid('Invalid shared token.')
    if cfg['auth_mode'] == 'token' and len(cfg['token']) < 32:
        raise Invalid('Set a shared token of 32â€“1024 characters.')
    if not isinstance(cfg['users'], list) or len(cfg['users']) > 64:
        raise Invalid('Use at most 64 users.')
    names = set()
    for user in cfg['users']:
        if not isinstance(user, dict) or set(user) != {'name', 'password', 'publish', 'subscribe'}:
            raise Invalid('Each user needs a name, password and two permission lists.')
        name = user['name']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', name) or name in names:
            raise Invalid('Usernames must be unique and use letters, numbers, dots, underscores or hyphens.')
        names.add(name)
        if not isinstance(user['password'], str) or not 16 <= len(user['password']) <= 1024:
            raise Invalid('Each user needs a password of 16â€“1024 characters.')
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
    # Supervisor can retain removed options across an upgrade. They have no effect.
    options.pop('restore_mode', None)
    options.pop('console_admin_user_ids', None)
    cfg = validate(options)
    legacy = DATA / 'console.json'
    if legacy.exists():
        prior = validate(json.loads(legacy.read_text()))
        if prior != cfg:
            raise Invalid('Previous console settings differ from HA Configuration. Copy the previous settings into HA Configuration and restart. No broker was started and existing data is preserved.')
    return cfg


def render(cfg):
    auth = {'token': cfg['token']} if cfg['auth_mode'] == 'token' else {
        'users': [dict(user=u['name'], password=u['password'], permissions={
            'publish': {'allow': u['publish']} if u['publish'] else {'deny': ['>']},
            'subscribe': {'allow': u['subscribe']} if u['subscribe'] else {'deny': ['>']}}) for u in cfg['users']]}
    result = dict(server_name='nats', listen='0.0.0.0:4222', authorization=auth,
                  jetstream=dict(store_dir='/data/jetstream', max_file_store=cfg['file_gb'] * 1024**3,
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
    prepare_tls(cfg)
    path = DATA / 'server.conf'
    atomic_file(path, json.dumps(render(cfg)).encode(), broker_readable=True)
    check = subprocess.run(['nats-server', '-t', '-c', str(path)], capture_output=True)
    if check.returncode:
        raise Invalid('NATS rejected the generated configuration; no settings were saved.')


def start_broker():
    global BROKER
    BROKER = subprocess.Popen(['su-exec', 'natsapp', 'nats-server', '-c', '/data/server.conf'], env={key: value for key, value in os.environ.items() if key != 'SUPERVISOR_TOKEN'})
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


def main():
    os.umask(0o077)
    DATA.mkdir(exist_ok=True)
    (DATA / 'jetstream').mkdir(mode=0o700, exist_ok=True)
    subprocess.run(['chown', '-R', 'natsapp:natsapp', str(DATA / 'jetstream')], check=True)
    os.chown(DATA, 0, 10001)
    DATA.chmod(0o750)
    def shutdown(*_):
        STOP.set()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    enrollment = None
    try:
        cfg = bootstrap()
        write_config(cfg)
        if STOP.is_set():
            return
        start_broker()
        if cfg['provision_nui'] and os.environ.get('SUPERVISOR_TOKEN'):
            import provision
            enrollment = provision.start(cfg)
        # Remove the superseded secret-bearing store only after a verified match
        # and successful start. HA Configuration is now the sole source of truth.
        (DATA / 'console.json').unlink(missing_ok=True)
        log('NATS is running with HA Configuration. Save and restart to change startup settings. Use NUI or NATS clients for live administration.')
        while not STOP.wait(1):
            if BROKER.poll() is not None:
                raise Invalid('NATS exited unexpectedly. Stopping for Supervisor recovery.')
    finally:
        if enrollment:
            enrollment.shutdown()
            enrollment.server_close()
        stop_broker()


if __name__ == '__main__':
    try:
        main()
    except Invalid as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
    except (OSError, ValueError, TypeError):
        print('Could not load startup configuration. Check HA Configuration, certificate files and free disk space.', flush=True)
        raise SystemExit(1) from None
