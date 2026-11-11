import json
from pathlib import Path
import unittest
from aip_parser import AIPSyntaxError, parse_aip


class TestSharedParserFixtures(unittest.TestCase):
    def test_shared_corpus(self):
        cases = json.loads(Path('tests/fixtures/parser_cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(name=case['name']):
                if case.get('invalid'):
                    with self.assertRaises(AIPSyntaxError) as caught:
                        parse_aip(case['source'])
                    self.assertGreaterEqual(caught.exception.line, 1)
                    self.assertGreaterEqual(caught.exception.column, 1)
                    continue
                ast = parse_aip(case['source'])
                expected = case['expected']
                self.assertEqual(ast.all_variables(), expected['variables'])
                self.assertEqual(ast.generate.to_json_schema() if ast.generate else None, expected['schema'])
                for key in ('model', 'temperature', 'options'):
                    if key in expected:
                        self.assertEqual(getattr(ast.generate, key), expected[key])
                if 'user_contains' in expected:
                    self.assertIn(expected['user_contains'], ast.user_prompt.raw_template)
