#!/usr/bin/env python3
"""
Unit tests for aip_runner.py CLI tool.
"""

import unittest
import subprocess
import json
import os
import sys

class TestAIPRunnerCLI(unittest.TestCase):

    def test_run_with_data_flag_outputs_pure_json(self):
        cmd = [
            sys.executable,
            "aip_runner.py",
            "run",
            "examples/examiner.aip",
            "--data",
            json.dumps({"name": "Grace Hopper", "text": "A compiler translates high-level code."}),
            "--mock"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")

        # STDOUT must be purely valid JSON
        stdout_str = proc.stdout.strip()
        parsed = json.loads(stdout_str)
        self.assertIn("score", parsed)
        self.assertIn("passed", parsed)
        self.assertIn("notes", parsed)

    def test_run_with_file_flag(self):
        cmd = [
            sys.executable,
            "aip_runner.py",
            "run",
            "examples/examiner.aip",
            "--file",
            "examples/data.json",
            "--mock"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        parsed = json.loads(proc.stdout.strip())
        self.assertTrue(isinstance(parsed, dict))

    def test_missing_variable_returns_exit_1_and_stderr(self):
        cmd = [
            sys.executable,
            "aip_runner.py",
            "run",
            "examples/examiner.aip",
            "--data",
            json.dumps({"name": "Incomplete"}),  # missing text
            "--mock"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[AIP Variable Error]", proc.stderr)
        self.assertIn("$text", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_invalid_json_data_returns_exit_1(self):
        cmd = [
            sys.executable,
            "aip_runner.py",
            "run",
            "examples/examiner.aip",
            "--data",
            "{not valid json}",
            "--mock"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[AIP Error]", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_missing_script_file_returns_exit_1(self):
        cmd = [
            sys.executable,
            "aip_runner.py",
            "run",
            "nonexistent_file.aip",
            "--data",
            "{}",
            "--mock"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Script file not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
