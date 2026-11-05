import importlib.util
from pathlib import Path
import unittest

NATIVE = Path(__file__).resolve().parents[1] / 'native'


def load(name):
    spec = importlib.util.spec_from_file_location(name, NATIVE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sandbox = load('sandbox')
egress = load('egress')


class NativeTests(unittest.TestCase):
    def test_payload_remains_argv_data_and_cannot_add_mounts(self):
        payload = ['/bin/echo', '--share-net', '$(touch /host)']
        cmd = sandbox.command(payload, 'tdk-sandbox-' + 'a' * 32)
        self.assertEqual(cmd[-3:], payload)
        self.assertEqual(cmd[-4], '--')
        self.assertIn('--expand-environment=no', cmd)
        self.assertIn('DynamicUser=yes', cmd)
        self.assertIn('--clearenv', cmd)
        self.assertIn('--unshare-all', cmd)
        self.assertIn('KillMode=control-group', cmd)
        self.assertIn('RuntimeMaxSec=60s', cmd)
        self.assertNotIn('--share-net', cmd[:-3])

    def test_invalid_control_inputs_fail_before_execution(self):
        for payload, name, seconds, memory in [([], 'tdk-sandbox-' + 'a'*32, 1, '1G'),
                (['echo'], 'tdk-sandbox-' + 'a'*32, 1, '1G'),
                (['/bin/true'], '../../other', 1, '1G'),
                (['/bin/true'], 'tdk-sandbox-' + 'a'*32, 0, '1G'),
                (['/bin/true'], 'tdk-sandbox-' + 'a'*32, 1, 'unlimited')]:
            with self.subTest(name=name, payload=payload), self.assertRaises(ValueError):
                sandbox.command(payload, name, seconds, memory)

    def test_firewall_scopes_only_runner_uid_and_denies_interface_subnets(self):
        script = egress.rules(996, [{'addr_info':[
            {'local':'192.0.2.8','prefixlen':24},
            {'local':'2001:db8:1::9','prefixlen':64}]}])
        self.assertIn('meta skuid 996 jump restricted', script)
        self.assertIn('policy accept', script)  # Other host accounts are untouched.
        self.assertIn('192.0.2.0/24', script)
        self.assertIn('2001:db8:1::/64', script)
        self.assertLess(script.index('127.0.0.53'), script.index('127.0.0.0/8'))
        self.assertLess(script.index('169.254.0.0/16'), script.index('tcp dport 443 accept'))
        self.assertNotIn('flush ruleset', script)


if __name__ == '__main__':
    unittest.main()
