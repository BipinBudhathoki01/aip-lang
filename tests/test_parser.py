#!/usr/bin/env python3
"""
Unit tests for the AIP DSL parser and AST generator.
"""

import unittest
from aip_parser import parse_aip, AIPParser, VariableToken, TextToken, TypeSpec


class TestAIPParser(unittest.TestCase):

    def setUp(self):
        self.parser = AIPParser()

    def test_sample_script(self):
        sample = """system:
    You are an expert examiner.

user:
    Analyze the following submission by {{ $name }}:
    "{{ $text }}"

generate as AnalysisResult {
    model: "gemini-2.0-flash",
    temperature: 0.2,
    schema: {
        score: int,
        passed: bool,
        notes: list[string]
    }
}
"""
        ast = self.parser.parse(sample)

        # 1. System Prompt Node
        self.assertIsNotNone(ast.system_prompt)
        self.assertEqual(len(ast.system_prompt.variables), 0)
        self.assertIn("You are an expert examiner.", ast.system_prompt.raw_template)

        # 2. User Prompt Node
        self.assertIsNotNone(ast.user_prompt)
        self.assertEqual(ast.user_prompt.variables, ["name", "text"])
        rendered = ast.user_prompt.render({"name": "Alice", "text": "Quantum Computing"})
        self.assertIn("Alice", rendered)
        self.assertIn("Quantum Computing", rendered)

        # 3. Generate Block
        self.assertIsNotNone(ast.generate)
        self.assertEqual(ast.generate.target_class, "AnalysisResult")
        self.assertEqual(ast.generate.model, "gemini-2.0-flash")
        self.assertEqual(ast.generate.temperature, 0.2)
        self.assertIn("score", ast.generate.schema)
        self.assertEqual(ast.generate.schema["score"].name, "int")
        self.assertIn("passed", ast.generate.schema)
        self.assertEqual(ast.generate.schema["passed"].name, "bool")
        self.assertIn("notes", ast.generate.schema)
        self.assertEqual(ast.generate.schema["notes"].name, "list")
        self.assertEqual(ast.generate.schema["notes"].type_args[0].name, "string")

        # 4. JSON Schema Generation
        js = ast.generate.to_json_schema()
        self.assertEqual(js["type"], "object")
        self.assertEqual(js["title"], "AnalysisResult")
        self.assertEqual(js["properties"]["score"]["type"], "integer")
        self.assertEqual(js["properties"]["passed"]["type"], "boolean")
        self.assertEqual(js["properties"]["notes"]["type"], "array")
        self.assertEqual(js["properties"]["notes"]["items"]["type"], "string")

    def test_system_prompt_with_variables(self):
        code = """system:
    Role: {{ $role }}. Tone: {{ $tone }}.

user:
    Hello {{ $user_name }}!

generate {
    model: "gemini-2.0-flash"
}
"""
        ast = self.parser.parse(code)
        self.assertEqual(ast.system_prompt.variables, ["role", "tone"])
        self.assertEqual(ast.user_prompt.variables, ["user_name"])
        self.assertIsNone(ast.generate.target_class)
        self.assertEqual(ast.generate.model, "gemini-2.0-flash")

    def test_nested_generic_types(self):
        code = """user:
    Generate tags.

generate as TagPayload {
    schema: {
        matrix: list[list[int]],
        lookup: dict[string, bool]
    }
}
"""
        ast = self.parser.parse(code)
        matrix_type = ast.generate.schema["matrix"]
        self.assertEqual(matrix_type.name, "list")
        self.assertEqual(matrix_type.type_args[0].name, "list")
        self.assertEqual(matrix_type.type_args[0].type_args[0].name, "int")

        lookup_type = ast.generate.schema["lookup"]
        self.assertEqual(lookup_type.name, "dict")
        self.assertEqual(len(lookup_type.type_args), 2)
        self.assertEqual(lookup_type.type_args[0].name, "string")
        self.assertEqual(lookup_type.type_args[1].name, "bool")

    def test_rendering_without_context_preserves_token(self):
        code = """user:
    Hello {{ $unprovided }}!
generate { model: "gemini-2.0-flash" }
"""
        ast = self.parser.parse(code)
        rendered = ast.user_prompt.render({})
        self.assertIn("{{ $unprovided }}", rendered)


if __name__ == "__main__":
    unittest.main()
