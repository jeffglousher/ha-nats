"""Reject private deployment material without printing matched values."""
from pathlib import Path
import ipaddress
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
PROXY_FILES = {'nats_nui/nginx.conf', 'nats_nui/tests/runtime.py'}
PATTERNS = {
    'personal Windows path': re.compile(r'(?i)[a-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\s]+'),
    'personal Unix path': re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+/'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'credential URL': re.compile(r'[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@', re.I),
}

def main():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    failures = []
    for name in filter(None, names):
        path = ROOT / name
        if not path.is_file():
            continue
        if path.is_symlink():
            failures.append((name, 'symlink requires explicit publication review'))
            continue
        if path.name in {'options.json', '.env', 'client.json', 'secrets.yaml'} or path.suffix in {'.key', '.pem', '.bundle', '.log', '.zip', '.gz'}:
            failures.append((name, 'private or generated file'))
        text = path.read_bytes().decode('utf-8', errors='ignore')
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append((name, label))
        for value in re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', text):
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            if any(address in network for network in NETWORKS):
                # Supervisor's documented ingress proxy, not a deployment address.
                if value == '172.30.32.2' and name in PROXY_FILES:
                    continue
                # Scanner policy contains the RFC1918 network definitions itself.
                if name == 'tools/check_privacy.py' and value in {'10.0.0.0', '172.16.0.0', '192.168.0.0', '172.30.32.2'}:
                    continue
                failures.append((name, 'private network address'))
    for name, reason in failures:
        print(f'FAIL: {name}: {reason}')
    if failures:
        return 1
    print(f'PASS: privacy checks across {len(list(filter(None, names)))} candidate files')
    return 0

if __name__ == '__main__':
    sys.exit(main())
