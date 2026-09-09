"""Configuration transactions and ingress boundary tests without a running broker."""
import copy
import json
from email.message import Message
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parent.parent / 'server.py'
if not source.exists():
    source = Path('/opt/nats-console/server.py')
spec = importlib.util.spec_from_file_location('console', source)
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.old = console.validate({'token': 'test-only-' + 'a' * 40})
        console.CURRENT = copy.deepcopy(self.old)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        mocked_data = patch.object(console, 'DATA', self.data)
        mocked_data.start()
        self.addCleanup(mocked_data.stop)

    def test_validation_does_not_touch_running_broker(self):
        with patch.object(console, 'stop_broker') as stop:
            with self.assertRaises(console.Invalid):
                console.apply({'token': 'short'})
            stop.assert_not_called()
        self.assertEqual(console.CURRENT, self.old)

    def test_rejected_generated_config_does_not_restart(self):
        with patch.object(console, 'write_config', side_effect=[console.Invalid('rejected'), None]) as write, patch.object(console, 'stop_broker') as stop, patch.object(console, 'restore_files') as restore:
            with self.assertRaises(console.Invalid):
                console.apply({**self.old, 'file_gb': 6})
            stop.assert_not_called()
            self.assertEqual(write.call_count, 1)

    def test_failed_start_restores_previous_configuration(self):
        with patch.object(console, 'write_config') as write, patch.object(console, 'stop_broker') as stop, patch.object(console, 'start_broker', side_effect=[console.Invalid('failed'), None]) as start, patch.object(console, 'atomic_file') as save:
            with self.assertRaises(console.Invalid):
                console.apply({**self.old, 'file_gb': 6})
            self.assertEqual(write.call_count, 1)
            self.assertEqual(start.call_count, 2)
            self.assertEqual(stop.call_count, 2)
            save.assert_not_called()
        self.assertEqual(console.CURRENT, self.old)

    def test_disk_failure_rolls_back_runtime(self):
        with patch.object(console, 'write_config') as write, patch.object(console, 'stop_broker'), patch.object(console, 'start_broker') as start, patch.object(console, 'atomic_file', side_effect=OSError('disk full')), patch.object(console, 'restore_files'):
            with self.assertRaises(OSError):
                console.apply({**self.old, 'file_gb': 6})
            self.assertEqual(start.call_count, 2)
            self.assertEqual(write.call_count, 1)
        self.assertEqual(console.CURRENT, self.old)

    def test_ingress_requires_one_allowed_identity(self):
        user = 'a' * 32
        (self.data / 'options.json').write_text(json.dumps({'console_admin_user_ids': [user]}))
        handler = object.__new__(console.Handler)
        cases = [
            ('127.0.0.1', [('X-Remote-User-Id', user), ('X-Forwarded-For', '172.30.32.2')], False),
            ('172.30.32.2', [('X-Remote-User-Id', user), ('Sec-Fetch-Site', 'cross-site')], False),
            ('172.30.32.2', [], False),
            ('172.30.32.2', [('X-Remote-User-Id', 'b' * 32)], False),
            ('172.30.32.2', [('X-Remote-User-Id', user), ('X-Remote-User-Id', user)], False),
            ('172.30.32.2', [('X-Remote-User-Id', user)], True),
        ]
        for peer, headers, expected in cases:
            handler.client_address = (peer, 12345)
            handler.headers = Message()
            for name, value in headers:
                handler.headers[name] = value
            self.assertEqual(handler.allowed(), expected)
        # Revoking access must affect the very next request, without restart.
        (self.data / 'options.json').write_text(json.dumps({'console_admin_user_ids': []}))
        self.assertFalse(handler.allowed())

    def test_invalid_identity_configuration_fails_closed(self):
        for ids in (None, 'a' * 32, ['A' * 32], ['../options.json'], [False], ['a' * 32] * 65):
            (self.data / 'options.json').write_text(json.dumps({'console_admin_user_ids': ids}))
            self.assertEqual(console.console_users(), ())
        (self.data / 'options.json').write_text('{invalid')
        self.assertEqual(console.console_users(), ())

    def test_failed_apply_restores_exact_deployed_tls_not_mutable_source(self):
        (self.data / 'tls').mkdir()
        original = {self.data / 'server.conf': b'original config',
                    self.data / 'tls/cert.pem': b'original certificate',
                    self.data / 'tls/key.pem': b'original key'}
        for path, content in original.items():
            path.write_bytes(content)
        source = self.data / 'renewed.pem'
        source.write_bytes(b'renewed certificate')
        def generated(_):
            (self.data / 'server.conf').write_bytes(b'candidate config')
            (self.data / 'tls/cert.pem').write_bytes(source.read_bytes())
            (self.data / 'tls/key.pem').write_bytes(b'candidate key')
            (self.data / 'tls/ca.pem').write_bytes(b'candidate ca')
            source.unlink()  # Renewal manager removes original source before recovery.
        def write(path, content, broker_readable=False):
            path.write_bytes(content)
        with patch.object(console, 'write_config', side_effect=generated) as generate, patch.object(console, 'atomic_file', side_effect=write), patch.object(console, 'stop_broker'), patch.object(console, 'start_broker', side_effect=[console.Invalid('failed'), None]) as start:
            with self.assertRaises(console.Invalid):
                console.apply({**self.old, 'file_gb': 6})
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(start.call_count, 2)
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertFalse((self.data / 'tls/ca.pem').exists())
        self.assertEqual(console.CURRENT, self.old)

    def test_certificate_symlink_cannot_escape_share(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'ssl').mkdir()
            (root / 'outside.pem').write_text('not a certificate')
            try:
                (root / 'ssl' / 'escape.pem').symlink_to(root / 'outside.pem')
            except OSError:
                self.skipTest('symlinks unavailable on this host')
            with patch.object(console, 'SSL', root / 'ssl'):
                with self.assertRaises(console.Invalid):
                    console.ssl_file('escape.pem')

    def test_atomic_write_replaces_link_without_touching_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'target').write_bytes(b'keep')
            try:
                (root / 'settings').symlink_to(root / 'target')
            except OSError:
                self.skipTest('symlinks unavailable on this host')
            console.atomic_file(root / 'settings', b'new')
            self.assertEqual((root / 'target').read_bytes(), b'keep')
            self.assertEqual((root / 'settings').read_bytes(), b'new')


if __name__ == '__main__':
    unittest.main()
