"""Configuration transactions and ingress boundary tests without a running broker."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / 'server.py'
if not source.exists():
    source = Path('/opt/nats-console/server.py')
spec = importlib.util.spec_from_file_location('console', source)
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.old = console.validate({'token': 'test-only-' + 'a' * 40})
        console.CURRENT = copy.deepcopy(self.old)

    def test_validation_does_not_touch_running_broker(self):
        with patch.object(console, 'stop_broker') as stop:
            with self.assertRaises(console.Invalid):
                console.apply({'token': 'short'})
            stop.assert_not_called()
        self.assertEqual(console.CURRENT, self.old)

    def test_rejected_generated_config_does_not_restart(self):
        with patch.object(console, 'write_config', side_effect=[console.Invalid('rejected'), None]) as write, patch.object(console, 'stop_broker') as stop:
            with self.assertRaises(console.Invalid):
                console.apply({**self.old, 'file_gb': 6})
            stop.assert_not_called()
            self.assertEqual(write.call_args.args[0], self.old)

    def test_failed_start_restores_previous_configuration(self):
        with patch.object(console, 'write_config') as write, patch.object(console, 'stop_broker') as stop, patch.object(console, 'start_broker', side_effect=[console.Invalid('failed'), None]) as start, patch.object(console, 'atomic_file') as save:
            with self.assertRaises(console.Invalid):
                console.apply({**self.old, 'file_gb': 6})
            self.assertEqual(write.call_args.args[0], self.old)
            self.assertEqual(start.call_count, 2)
            self.assertEqual(stop.call_count, 2)
            save.assert_not_called()
        self.assertEqual(console.CURRENT, self.old)

    def test_disk_failure_rolls_back_runtime(self):
        with patch.object(console, 'write_config') as write, patch.object(console, 'stop_broker'), patch.object(console, 'start_broker') as start, patch.object(console, 'atomic_file', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                console.apply({**self.old, 'file_gb': 6})
            self.assertEqual(start.call_count, 2)
            self.assertEqual(write.call_args.args[0], self.old)
        self.assertEqual(console.CURRENT, self.old)

    def test_ingress_checks_peer_and_cross_site(self):
        handler = object.__new__(console.Handler)
        for peer, headers, expected in [
            ('127.0.0.1', {'X-Forwarded-For': '172.30.32.2'}, False),
            ('172.30.32.2', {'Sec-Fetch-Site': 'cross-site'}, False),
            ('172.30.32.2', {'Sec-Fetch-Site': 'same-origin'}, True),
        ]:
            handler.client_address = (peer, 12345)
            handler.headers = headers
            self.assertEqual(handler.allowed(), expected)

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
