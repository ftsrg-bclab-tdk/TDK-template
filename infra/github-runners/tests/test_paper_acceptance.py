import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'session'))
import paper


class PaperReceiptTests(unittest.TestCase):
    def exercise(self,results):
        with tempfile.TemporaryDirectory() as tmp,contextlib.chdir(tmp):
            Path('project.json').write_text('{"role":"project"}')
            with patch.object(paper.subprocess,'run',side_effect=results), \
                 patch.dict(os.environ,{'GITHUB_RUN_ID':'42','GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'a'*40}), \
                 contextlib.redirect_stdout(io.StringIO()):
                try:exit_code=paper.check()
                except KeyboardInterrupt:exit_code=130
            report=json.loads(Path('.project/checks/bme-acceptance.json').read_text())
            self.assertEqual(report['run_id'],'42')
            self.assertEqual(report['run_attempt'],'2')
            self.assertEqual(report['source_sha'],'a'*40)
            return exit_code,report

    def test_timeout_preserves_completed_records_and_failed_command_identity(self):
        code,report=self.exercise([subprocess.CompletedProcess([],0),subprocess.TimeoutExpired(['paper'],1800)])
        self.assertEqual(code,1)
        self.assertEqual([r['name'] for r in report['commands']],['runtime','paper'])
        self.assertEqual(report['commands'][0]['exit_code'],0)
        failed=report['commands'][1]
        self.assertEqual(failed['exit_code'],124);self.assertEqual(failed['error'],'timeout')
        self.assertEqual(failed['timeout_seconds'],1800)
        self.assertGreaterEqual(failed['completed_at'],failed['started_at'])

    def test_runtime_timeout_stops_dependent_checks_and_writes_receipt(self):
        code,report=self.exercise([subprocess.TimeoutExpired(['runtime'],1800)])
        self.assertEqual(code,1);self.assertEqual(len(report['commands']),1)

    def test_launch_failure_writes_failed_receipt(self):
        code,report=self.exercise([FileNotFoundError('fixture')])
        self.assertEqual(code,1)
        self.assertEqual(report['commands'][0]['exit_code'],127)

    def test_interrupt_preserves_partial_receipt_and_propagates(self):
        code,report=self.exercise([subprocess.CompletedProcess([],0),KeyboardInterrupt()])
        self.assertEqual(code,130)
        self.assertEqual(report['commands'][-1]['error'],'KeyboardInterrupt')


if __name__=='__main__':unittest.main()
