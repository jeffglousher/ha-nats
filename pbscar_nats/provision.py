"""Companion NUI enrollment over HA's private app network; no host port."""
import ipaddress
import json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

NUI_SLUG = '8053b95a_nats_nui'

def info(slug):
    request = urllib.request.Request('http://supervisor/addons/' + slug + '/info',
        headers={'Authorization': 'Bearer ' + os.environ['SUPERVISOR_TOKEN']})
    with urllib.request.urlopen(request, timeout=3) as response:
        result = json.load(response)
    if result.get('result') != 'ok':
        raise ValueError('Supervisor metadata unavailable')
    return result['data']

def permitted(peer, metadata):
    try:
        return metadata.get('state') == 'started' and ipaddress.ip_address(peer) == ipaddress.ip_address(metadata['ip_address'])
    except (ValueError, KeyError):
        return False

def connection(cfg, hostname):
    # Do not weaken TLS, choose a privileged user or distribute client keys.
    # Non-token and TLS deployments use NUI's regular connection setup.
    if cfg['tls'] or cfg['auth_mode'] != 'token':
        return None
    return dict(name='Local NATS', hosts=['nats://' + hostname + ':4222'],
        auth=[dict(mode='auth_token', active=True, token=cfg['token'])],
        tls_auth=dict(enabled=False), subscriptions=[],
        metrics=dict(http_source=dict(active=False), nats_source=dict(active=False)))

def start(cfg):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)
        def log_message(self, *_):
            pass
        def do_GET(self):
            body = b''
            status = 403
            try:
                if self.path == '/connection' and permitted(self.client_address[0], info(NUI_SLUG)):
                    value = connection(cfg, info('self')['hostname'])
                    status = 200 if value else 409
                    body = json.dumps(value or {'error': 'Configure this authentication/TLS mode directly in NUI.'}).encode()
            except Exception:
                status = 503
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = HTTPServer(('0.0.0.0', 8098), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
