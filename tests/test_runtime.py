#!/usr/bin/env python3
"""
Unit tests for AIP Execution Runtime, Variable Enforcement, Dynamic Schema, and Auto-Healing.
"""

import unittest
import json
from aip_parser import parse_aip
from aip_runtime import (
    run_aip,
    ast_to_pydantic_model,
    MockGeminiClient,
    AIPExecutionError,
)

SAMPLE_CODE = """system:
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

class TestAIPRuntime(unittest.TestCase):

    def setUp(self):
        self.ast = parse_aip(SAMPLE_CODE)

    def test_missing_variable_raises_key_error(self):
        # Missing $name
        with self.assertRaises(KeyError) as ctx:
            run_aip(self.ast, {"text": "Hello"})
        self.assertIn("$name", str(ctx.exception))

        # Missing $text
        with self.assertRaises(KeyError) as ctx:
            run_aip(self.ast, {"name": "Ada"})
        self.assertIn("$text", str(ctx.exception))

    def test_successful_execution(self):
        client = MockGeminiClient([
            json.dumps({"score": 100, "passed": True, "notes": ["Perfect!"]})
        ])
        result = run_aip(self.ast, {"name": "Ada", "text": "My paper"}, client=client)
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["passed"])
        self.assertEqual(result["notes"], ["Perfect!"])

    def test_auto_healing_recovery(self):
        client = MockGeminiClient([
            # Attempt 1: bad json
            '{"score": 90, "passed":',
            # Attempt 2: bad types
            '{"score": "not_an_int", "passed": false, "notes": []}',
            # Attempt 3: healed
            '{"score": 90, "passed": true, "notes": ["Healed"]}',
        ])
        result = run_aip(self.ast, {"name": "Grace", "text": "Compiler"}, client=client, max_retries=2)
        self.assertEqual(result["score"], 90)
        self.assertTrue(result["passed"])
        self.assertEqual(len(client.calls), 3)

    def test_max_retries_exceeded_raises_error(self):
        client = MockGeminiClient([
            '{"invalid": "always"}',
            '{"invalid": "still"}',
            '{"invalid": "never_fixes"}',
        ])
        with self.assertRaises(AIPExecutionError):
            run_aip(self.ast, {"name": "Test", "text": "Code"}, client=client, max_retries=2)

    def test_dynamic_pydantic_model_types(self):
        model = ast_to_pydantic_model(self.ast.generate.schema, "CustomResult")
        schema = model.model_json_schema()
        self.assertEqual(schema["title"], "CustomResult")
        self.assertEqual(schema["properties"]["score"]["type"], "integer")
        self.assertEqual(schema["properties"]["passed"]["type"], "boolean")
        self.assertEqual(schema["properties"]["notes"]["type"], "array")


if __name__ == "__main__":
    unittest.main()
