"""Runner contract tests using a fake make (no simulator/license required)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / 'src/sim/scripts/run_regress.py'


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, PATH=str(self.dir) + os.pathsep + os.environ['PATH'])
        fake = self.dir / 'make'
        fake.write_text('''#!/usr/bin/env python3
import sys, time
v = dict(x.split('=', 1) for x in sys.argv[1:] if '=' in x)
case = v.get('TC', '')
if case == 'timeout':
    time.sleep(30)
elif case == 'error':
    print('compile failed')
    sys.exit(2)
elif case == 'missing':
    print('simulation finished without result')
elif case == 'fail':
    print('TEST FAILED: mismatch')
elif case == 'both':
    print('TEST PASSED (early)')
    print('TEST FAILED: late mismatch')
elif case == 'watchdog':
    print('TEST FAILED: TIMEOUT watchdog')
else:
    print('TEST PASSED (done)')
''')
        fake.chmod(0o755)

    def run_runner(self, *args):
        return subprocess.run([sys.executable, str(RUNNER), *map(str, args)],
                              env=self.env, capture_output=True, text=True, timeout=15)

    def test_statuses_continue_and_replay(self):
        patterns = self.dir / 'pat.list'
        patterns.write_text('# comment\n// comment\n' + ''.join(
            f'tb {case}\n' for case in ('pass', 'fail', 'error', 'timeout', 'missing', 'both', 'watchdog', 'pass')))
        p = self.run_runner(patterns, '--sim', 'verilator', '--timeout', '0.5')
        self.assertEqual(p.returncode, 1, p.stderr)
        run = Path(p.stdout.splitlines()[0].split(': ', 1)[1])
        self.addCleanup(shutil.rmtree, run)
        data = json.loads((run / 'results.json').read_text())
        self.assertEqual([r['status'] for r in data['results']],
                         ['PASS', 'FAIL', 'ERROR', 'TIMEOUT', 'ERROR', 'FAIL', 'TIMEOUT', 'PASS'])
        self.assertTrue(all(Path(r['log']).exists() for r in data['results']))
        replay = self.run_runner('--report', run)
        self.assertEqual(replay.returncode, 1)
        self.assertEqual(replay.stdout, (run / 'report.txt').read_text())

    def test_empty_and_malformed_lists(self):
        patterns = self.dir / 'pat.list'
        for text in ('# empty\n', 'tb\n', 'tb tc SIM=questa\n', 'tb tc not_an_assignment\n'):
            patterns.write_text(text)
            p = self.run_runner(patterns)
            self.assertEqual(p.returncode, 2)
            self.assertNotIn('Report directory:', p.stdout)

    def test_seed_expansion_and_assignment_precedence(self):
        patterns = self.dir / 'pat.list'
        patterns.write_text('tb pass PARAMS="P=4" # inline comment\n')
        p = self.run_runner(patterns, '--seeds', '7,8', '--var', 'PARAMS=P=8')
        self.assertEqual(p.returncode, 0, p.stderr)
        run = Path(p.stdout.splitlines()[0].split(': ', 1)[1])
        self.addCleanup(shutil.rmtree, run)
        data = json.loads((run / 'results.json').read_text())
        self.assertEqual([r['seed'] for r in data['results']], ['7', '8'])
        self.assertTrue(all(r['command'][-2:] == ['PARAMS=P=8', 'PARAMS=P=4'] for r in data['results']))


if __name__ == '__main__':
    unittest.main()
