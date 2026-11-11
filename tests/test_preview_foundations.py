import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aip_runtime
from aip_parser import parse_aip
from aip_runtime import ast_to_pydantic_model, run_aip
from aip_lang.codegen_python import generate_python_code
from aip_lang.codegen_php import generate_php_code
from pydantic import ValidationError


class TestExplicitMockExecution(unittest.TestCase):
    def test_missing_cloud_keys_do_not_return_fixtures(self):
        with patch.dict(os.environ, {}, clear=True):
            for provider, key in [('gemini', 'GEMINI_API_KEY'), ('openai', 'OPENAI_API_KEY'), ('anthropic', 'ANTHROPIC_API_KEY'), ('groq', 'GROQ_API_KEY')]:
                code = f'user:\nHello\ngenerate {{provider:"{provider}", schema:{{answer:string}}}}'
                with self.subTest(provider=provider), self.assertRaisesRegex(ValueError, key):
                    run_aip(code, {})

    def test_explicit_mock_supports_non_examiner_nested_schemas(self):
        code = 'user:\nHello\ngenerate {schema:{person:{name:string,active:bool},amount:float,items:list[int],lookup:dict[string,int]}}'
        with patch.dict(os.environ, {}, clear=True):
            result = run_aip(code, {}, mock=True)
        self.assertEqual(result, {'person': {'name': 'Mock value', 'active': False}, 'amount': 0.0, 'items': [], 'lookup': {}})

    def test_missing_sdk_does_not_fall_back(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=True), patch.object(aip_runtime, 'HAS_GENAI', False), self.assertRaisesRegex(RuntimeError, 'google-genai'):
            run_aip('user:\nHello\ngenerate {schema:{answer:string}}', {})

    def test_cli_requires_explicit_mock_and_labels_it_on_stderr(self):
        env = {key: value for key, value in os.environ.items() if key != 'GEMINI_API_KEY'}
        command = [sys.executable, 'aip_runner.py', 'run', 'examples/invoice-extraction.aiprompt', '--file', 'examples/invoice-extraction-data.json']
        failure = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, '')
        self.assertIn('GEMINI_API_KEY', failure.stderr)
        self.assertIn('[AIP Configuration Error]', failure.stderr)
        success = subprocess.run(command + ['--mock'], env=env, capture_output=True, text=True)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn('[AIP Mock]', success.stderr)
        fixture = json.loads(success.stdout)
        self.assertEqual(fixture['vendor']['name'], 'Mock value')
        self.assertEqual(fixture['items'], [])
        self.assertEqual(fixture['total'], 0)


class TestCliDiagnostics(unittest.TestCase):
    def test_parse_errors_show_source_coordinates_and_no_traceback(self):
        cases = ['user:\nHello\ngenerate {schema:{score:int}', 'user:\nHello\ngenerate {schema:{score int}}', 'user:\nHello\ngenerate {schema:{score:decimal}}']
        for code in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'invalid.aiprompt'
                path.write_text(code, encoding='utf-8')
                for action in ('check', 'schema', 'compile', 'run'):
                    result = subprocess.run([sys.executable, 'aip_runner.py', action, str(path)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, '')
                    self.assertRegex(result.stderr, r'Line \d+, column \d+')
                    self.assertIn('^', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)


class TestInvoiceExample(unittest.TestCase):
    def test_reference_result_matches_shipped_contract(self):
        ast = parse_aip(Path('examples/invoice-extraction.aiprompt').read_text(encoding='utf-8'))
        reference = json.loads(Path('examples/invoice-extraction-result.json').read_text(encoding='utf-8'))
        model = ast_to_pydantic_model(ast.generate.schema)
        self.assertEqual(model.model_validate(reference).model_dump(), reference)
        invalid = {**reference, 'items': [{'description': 'Notebook', 'quantity': 'two', 'unit_price': 12.5}]}
        with self.assertRaises(ValidationError):
            model.model_validate(invalid)

    def test_generated_python_validates_invoice_reference(self):
        ast = parse_aip(Path('examples/invoice-extraction.aiprompt').read_text(encoding='utf-8'))
        reference = json.loads(Path('examples/invoice-extraction-result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invoice.py'
            path.write_text(generate_python_code(ast), encoding='utf-8')
            spec = importlib.util.spec_from_file_location('invoice_example', path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
                self.assertEqual(module.InvoiceResult.model_validate(reference).model_dump(), reference)
            finally:
                sys.modules.pop(spec.name, None)

    @unittest.skipUnless(shutil.which('php'), 'PHP not installed')
    def test_generated_php_validates_invoice_reference(self):
        ast = parse_aip(Path('examples/invoice-extraction.aiprompt').read_text(encoding='utf-8'))
        reference = json.loads(Path('examples/invoice-extraction-result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'InvoiceExtractionAip.php'
            path.write_text(generate_php_code(ast, class_name='InvoiceExtractionAip'), encoding='utf-8')
            runner = Path(directory) / 'validate.php'
            runner.write_text("<?php require $argv[1]; echo json_encode(\\App\\AI\\InvoiceExtractionAip::validateOutput(stream_get_contents(STDIN)));", encoding='utf-8')
            result = subprocess.run(['php', str(runner), str(path)], input=json.dumps(reference), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), reference)
