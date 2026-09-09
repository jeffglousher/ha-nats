"""HA startup configuration, safe legacy migration and filesystem boundaries."""
import json
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
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        mocked_data = patch.object(console, 'DATA', self.data)
        mocked_data.start()
        self.addCleanup(mocked_data.stop)

    def test_ha_options_are_authoritative(self):
        desired = {**self.old, 'file_gb': 7, 'max_connections': 90}
        (self.data / 'options.json').write_text(json.dumps(desired))
        self.assertEqual(console.bootstrap(), desired)

    def test_legacy_mismatch_fails_without_modifying_data(self):
        (self.data / 'options.json').write_text(json.dumps(self.old))
        legacy = {**self.old, 'file_gb': 9}
        path = self.data / 'console.json'
        path.write_text(json.dumps(legacy))
        with self.assertRaises(console.Invalid):
            console.bootstrap()
        self.assertEqual(json.loads(path.read_text()), legacy)

    def test_matching_legacy_settings_can_start(self):
        (self.data / 'options.json').write_text(json.dumps(self.old))
        (self.data / 'console.json').write_text(json.dumps(self.old))
        self.assertEqual(console.bootstrap(), self.old)

    def test_obsolete_restore_mode_cannot_expand_storage(self):
        options = {**self.old, 'restore_mode': True, 'console_admin_user_ids': []}
        (self.data / 'options.json').write_text(json.dumps(options))
        rendered = console.render(console.bootstrap())
        self.assertEqual(rendered['jetstream']['max_file_store'], 5 * 1024**3)

    def test_bad_startup_values_fail_closed(self):
        for change in ({'file_gb': 0}, {'memory_mb': True}, {'unknown': 1},
                       {'auth_mode': 'none'}, {'token': ''}, {'tls': 'false'}):
            with self.assertRaises(console.Invalid):
                console.validate({**self.old, **change})

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
