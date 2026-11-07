import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest

from run import merge_reports
import test_project


class OrchestrationTests(unittest.TestCase):
    setUp = test_project.ProjectTests.setUp
    run_report = test_project.ProjectTests.run_report
    def test_aggregate_missing_selected_result_is_failure(self):
        report = self.run_report()
        config, digest = __import__('ci.config',fromlist=['load_project']).load_project(self.root)
        aggregate = merge_reports(report["plan"],{},self.root/".project/checks",config,digest,report["execution"]["started_at"])
        self.assertEqual(aggregate["gate_outcome"],"fail")
        self.assertEqual(aggregate["components"]["paper"]["outcome"],"unknown")

    def test_aggregate_requires_matching_component_identity(self):
        report = self.run_report()
        config, digest = __import__('ci.config',fromlist=['load_project']).load_project(self.root)
        wrong=copy.deepcopy(report)
        wrong["source"]["tested_sha"]="b"*40
        with self.assertRaisesRegex(ValueError,"identity"):
            merge_reports(report["plan"],{"paper":wrong},self.root/".project/checks",config,digest,report["execution"]["started_at"])

    def test_successful_steps_cannot_hide_source_change_failure(self):
        report=self.run_report()
        config,digest=__import__('ci.config',fromlist=['load_project']).load_project(self.root)
        report.update(gate_outcome="fail",error="Tracked source changed during execution")
        aggregate=merge_reports(report["plan"],{"paper":report},self.root/".project/checks",config,digest,report["execution"]["started_at"])
        self.assertEqual(aggregate["gate_outcome"],"fail")
