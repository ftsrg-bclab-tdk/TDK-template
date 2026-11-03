import unittest
from tlc import configuration, outcome


class TLCTests(unittest.TestCase):
    def test_configuration_is_explicit(self):
        self.assertEqual(configuration('CONSTANT Limit = 3\nINIT Init\nNEXT Next\nINVARIANTS Safe TypeOK'),
                         ({'Limit': 3}, ['Safe', 'TypeOK']))
        for bad in ('INIT Init\nNEXT Next', 'INIT Init\nNEXT Next\nINVARIANT Safe Safe',
                    'INIT Init\nNEXT Next\nINVARIANT Safe\nCONSTRAINT Hidden',
                    'INIT Init\nNEXT Next\nINVARIANT Safe\nPROPERTY Live'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                configuration(bad)

    def test_zero_exit_requires_complete_nonempty_search(self):
        success = 'Model checking completed. No error has been found.\n5 states generated, 4 distinct states found, 0 states left on queue.'
        self.assertEqual(outcome(0, success, ['Safe'])[0], 'verified')
        for code, text in ((0, ''), (1, success), (124, success), (0, success.replace('4 distinct', '0 distinct')),
                           (0, success.replace('0 states left', '1 states left')), (0, success + '\nError: bad')):
            with self.subTest(code=code, text=text):
                self.assertEqual(outcome(code, text, ['Safe'])[0], 'unknown')

    def test_violation_preserves_unchecked_obligations(self):
        summary, rows, _ = outcome(12, 'Error: Invariant Safe is violated.', ['Safe', 'TypeOK'])
        self.assertEqual(summary, 'violated')
        self.assertEqual(rows, [{'id': 'Safe', 'outcome': 'violated'}, {'id': 'TypeOK', 'outcome': 'unknown'}])
        self.assertEqual(outcome(12, 'Syntax error', ['Safe'])[0], 'unknown')
        self.assertEqual(outcome(124, 'Error: Invariant Safe is violated.', ['Safe'])[0], 'unknown')


if __name__ == '__main__':
    unittest.main()
