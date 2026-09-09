import importlib.util
import unittest
spec=importlib.util.spec_from_file_location('provision','/opt/nats-console/provision.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class Tests(unittest.TestCase):
    def test_actual_peer_only(self):
        metadata={'state':'started','ip_address':'192.0.2.4'}
        self.assertTrue(p.permitted('192.0.2.4',metadata))
        for peer in ('127.0.0.1','192.0.2.2','192.0.2.5','invalid'):
            self.assertFalse(p.permitted(peer,metadata))
        self.assertFalse(p.permitted('192.0.2.4',{}))
        self.assertFalse(p.permitted('192.0.2.4',{**metadata,'state':'stopped'}))
    def test_never_downgrades_tls_or_selects_user(self):
        cfg={'tls':False,'auth_mode':'token','token':'unit-test-token'}
        result=p.connection(cfg,'broker')
        self.assertEqual(result['hosts'],['nats://broker:4222'])
        self.assertEqual(result['auth'][0]['token'],cfg['token'])
        self.assertIsNone(p.connection({**cfg,'tls':True},'broker'))
        self.assertIsNone(p.connection({**cfg,'auth_mode':'users'},'broker'))

unittest.main()
