"""Exercise generated programs offline, including nested schema failures."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pydantic import ValidationError
from aip_parser import parse_aip
from aip_lang.codegen_python import generate_python_code
from aip_lang.codegen_php import generate_php_code
from aip_runtime import ast_to_pydantic_model
from playground_runner import process

SOURCE = '''system:
    Extract data, preserving "quotes" and C:\\notes.
user:
    Hello {{ $name }}.
generate as Result {
    model: "gemini-3.8-flash",
    schema: {
        count: int,
        author: { name: string, verified: bool },
        entries: list[{ value: int }],
        scores: dict[string, int]
    }
}
'''
VALID = {"count": 2, "author": {"name": "Ada", "verified": True}, "entries": [{"value": 4}], "scores": {"one": 1}}


class TestCodeGeneration(unittest.TestCase):
    def test_python_generated_nested_models_and_strict_validation(self):
        ast = parse_aip(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'compiled_prompt.py'
            path.write_text(generate_python_code(ast), encoding='utf-8')
            spec = importlib.util.spec_from_file_location('compiled_prompt', path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
                self.assertEqual(module.Result.model_validate(VALID).model_dump(), VALID)
                for invalid in self.invalid_payloads():
                    with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                        module.Result.model_validate(invalid)
            finally:
                sys.modules.pop(spec.name, None)

    @staticmethod
    def invalid_payloads():
        return [
            {**VALID, 'count': '2'},
            {**VALID, 'author': {'name': 'Ada', 'verified': 'true'}},
            {**VALID, 'entries': [{'value': '4'}]},
            {**VALID, 'scores': {'one': '1'}},
            {**VALID, 'extra': True},
            {key: value for key, value in VALID.items() if key != 'count'},
        ]

    @unittest.skipUnless(shutil.which('php'), 'PHP not installed')
    def test_php_generated_program_validates_nested_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Executor.php'
            path.write_text(generate_php_code(parse_aip(SOURCE)), encoding='utf-8')
            lint = subprocess.run(['php', '-l', str(path)], capture_output=True, text=True)
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
            runner = Path(directory) / 'run.php'
            runner.write_text("<?php\nrequire $argv[1];\ntry { $result = \\App\\AI\\AipExecutor::validateOutput(stream_get_contents(STDIN)); echo json_encode($result); } catch (Throwable $error) { fwrite(STDERR, $error->getMessage()); exit(1); }", encoding='utf-8')
            success = subprocess.run(['php', str(runner), str(path)], input=json.dumps(VALID), capture_output=True, text=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(json.loads(success.stdout), VALID)
            for invalid in self.invalid_payloads():
                with self.subTest(invalid=invalid):
                    result = subprocess.run(['php', str(runner), str(path)], input=json.dumps(invalid), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)

    def test_runtime_rejects_nested_coercions(self):
        model = ast_to_pydantic_model(parse_aip(SOURCE).generate.schema)
        for invalid in self.invalid_payloads():
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                model.model_validate(invalid)

    def test_playground_uses_submitted_source_and_variables(self):
        result = process({'code': SOURCE, 'variables': {'name': 'Grace'}, 'action': 'run'})
        self.assertIn('Grace', result['user'])
        self.assertEqual(result['mode'], 'mock')
        self.assertEqual(result['result']['author'], {'name': 'Mock value', 'verified': False})
        self.assertIn('scores', result['result'])

    def test_extensions_are_compatible(self):
        from aip_parser import AIPParser
        parser = AIPParser()
        preferred = parser.parse_file('examples/examiner.aiprompt')
        legacy = parser.parse_file('examples/examiner.aip')
        self.assertEqual(preferred.generate.to_json_schema(), legacy.generate.to_json_schema())
