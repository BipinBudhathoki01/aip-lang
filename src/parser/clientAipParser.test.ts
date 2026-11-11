import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAipClient } from './clientAipParser';

const SAMPLE_AIP = `system:
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
`;

test('client parser extracts system, user, and generate blocks', () => {
  const result = parseAipClient(SAMPLE_AIP);
  assert.equal(result.error, null);
  assert.notEqual(result.ast, null);

  const ast = result.ast!;
  assert.notEqual(ast.system_prompt, null);
  assert.notEqual(ast.user_prompt, null);
  assert.notEqual(ast.generate, null);

  // Variables
  assert.deepEqual(ast.user_prompt?.variables, ['name', 'text']);
  assert.deepEqual(ast.system_prompt?.variables, []);

  // Generate metadata
  assert.equal(ast.generate?.target_class, 'AnalysisResult');
  assert.equal(ast.generate?.model, 'gemini-2.0-flash');
  assert.equal(ast.generate?.temperature, 0.2);

  // Schema properties
  assert.equal(ast.generate?.schema.score.name, 'int');
  assert.equal(ast.generate?.schema.passed.name, 'bool');
  assert.equal(ast.generate?.schema.notes.name, 'list');
  assert.equal(ast.generate?.schema.notes.type_args?.[0].name, 'string');

  // JSON schema output
  const jsonSchema = ast.generate?.json_schema;
  assert.equal(jsonSchema?.type, 'object');
  assert.equal(jsonSchema?.title, 'AnalysisResult');
  assert.equal(jsonSchema?.properties.score.type, 'integer');
  assert.equal(jsonSchema?.properties.passed.type, 'boolean');
  assert.equal(jsonSchema?.properties.notes.type, 'array');
  assert.equal(jsonSchema?.properties.notes.items.type, 'string');
});

test('nested objects and dictionaries retain their complete schema', () => {
  const result = parseAipClient(`user:
    Hello {{ $name }}
generate as Payload {
    schema: { author: { name: string, verified: bool }, entries: list[{ value: int }], scores: dict[string, int] }
}`);
  assert.equal(result.error, null);
  const schema = result.ast!.generate!.json_schema;
  assert.equal(schema.properties.author.properties.verified.type, 'boolean');
  assert.equal(schema.properties.entries.items.properties.value.type, 'integer');
  assert.equal(schema.properties.scores.additionalProperties.type, 'integer');
  assert.deepEqual(schema.required, ['author', 'entries', 'scores']);
});
