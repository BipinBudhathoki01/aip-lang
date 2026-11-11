#!/usr/bin/env python3
"""
AIP (AI Scripting DSL) Parser using Lark EBNF.
Domain-Specific Language file extension: .aip

Parses prompt files containing:
- system: prompt with raw text and {{ $var }} tokens
- user: prompt with raw text and {{ $var }} tokens
- generate as TargetClass { model, temperature, schema { field: type } }

Outputs a strongly-typed Abstract Syntax Tree (AST).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union
import json
import sys
from lark import Lark, Transformer, Token, Tree

# ---------------------------------------------------------------------------
# 1. Formal Lark EBNF Grammar
# ---------------------------------------------------------------------------

AIP_GRAMMAR = r"""
?start: script

script: section+

?section: system_block
        | user_block
        | generate_block

system_block: "system" ":" prompt_content
user_block: "user" ":" prompt_content

prompt_content: prompt_item+
?prompt_item: var_ref | TEXT_FRAGMENT

// Variable interpolation syntax: {{ $var_name }}
var_ref: "{{" "$" CNAME "}}"

// Text fragment: matches any character until a variable tag {{
// or a top-level section header (system:, user:, or generate [...]{)
TEXT_FRAGMENT: /(?:(?!\{\{|\b(?:system|user)\s*:|\bgenerate\b(?:\s+as\s+[a-zA-Z_]\w*)?\s*\{)[\s\S])+/

// Generate block: specifies target class, model options, and schema
generate_block: "generate" ["as" CNAME] "{" [config_entries] "}"

config_entries: config_entry ("," config_entry)* [","]
config_entry: CNAME ":" value

?value: ESCAPED_STRING   -> string_val
      | SIGNED_NUMBER    -> number_val
      | boolean_val
      | schema_block

boolean_val: "true"  -> bool_true
           | "false" -> bool_false

schema_block: "{" [schema_fields] "}"
schema_fields: schema_field ("," schema_field)* [","]
schema_field: CNAME ":" type_spec

?type_spec: CNAME ("[" type_spec ("," type_spec)* "]")? -> type_spec_rule
          | "{" [schema_fields] "}"                      -> nested_schema_rule

%import common.CNAME
%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
"""

# ---------------------------------------------------------------------------
# 2. Abstract Syntax Tree (AST) Data Structures
# ---------------------------------------------------------------------------

@dataclass
class VariableToken:
    """Represents a dynamic variable placeholder like {{ $name }}."""
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "variable", "name": self.name}

    def __repr__(self) -> str:
        return f"VariableToken('${self.name}')"


@dataclass
class TextToken:
    """Represents a chunk of static prompt text."""
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "text", "text": self.text}

    def __repr__(self) -> str:
        return f"TextToken({repr(self.text)})"


PromptToken = Union[TextToken, VariableToken]


@dataclass
class SystemPromptNode:
    """AST node for the 'system:' prompt section."""
    tokens: List[PromptToken] = field(default_factory=list)

    @property
    def raw_template(self) -> str:
        """Returns the reconstructed template string."""
        return "".join(
            f"{{{{ ${t.name} }}}}" if isinstance(t, VariableToken) else t.text
            for t in self.tokens
        )

    @property
    def variables(self) -> List[str]:
        """Returns ordered unique variable names found in the system prompt."""
        seen = set()
        res = []
        for t in self.tokens:
            if isinstance(t, VariableToken) and t.name not in seen:
                seen.add(t.name)
                res.append(t.name)
        return res

    def render(self, context: Dict[str, Any]) -> str:
        """Interpolates variables using the provided dictionary."""
        return "".join(
            str(context[t.name]) if isinstance(t, VariableToken) and t.name in context
            else f"{{{{ ${t.name} }}}}" if isinstance(t, VariableToken)
            else t.text
            for t in self.tokens
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": [t.to_dict() for t in self.tokens],
            "raw_template": self.raw_template,
            "variables": self.variables,
        }


@dataclass
class UserPromptNode:
    """AST node for the 'user:' prompt section."""
    tokens: List[PromptToken] = field(default_factory=list)

    @property
    def raw_template(self) -> str:
        """Returns the reconstructed template string."""
        return "".join(
            f"{{{{ ${t.name} }}}}" if isinstance(t, VariableToken) else t.text
            for t in self.tokens
        )

    @property
    def variables(self) -> List[str]:
        """Returns ordered unique variable names found in the user prompt."""
        seen = set()
        res = []
        for t in self.tokens:
            if isinstance(t, VariableToken) and t.name not in seen:
                seen.add(t.name)
                res.append(t.name)
        return res

    def render(self, context: Dict[str, Any]) -> str:
        """Interpolates variables using the provided dictionary."""
        return "".join(
            str(context[t.name]) if isinstance(t, VariableToken) and t.name in context
            else f"{{{{ ${t.name} }}}}" if isinstance(t, VariableToken)
            else t.text
            for t in self.tokens
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": [t.to_dict() for t in self.tokens],
            "raw_template": self.raw_template,
            "variables": self.variables,
        }


@dataclass
class TypeSpec:
    """
    Represents a type specification in the schema block.
    Supports primitives ('int', 'bool', 'string') and generics ('list[string]', 'dict[string, int]').
    """
    name: str
    type_args: List["TypeSpec"] = field(default_factory=list)
    fields: Optional[Dict[str, "TypeSpec"]] = None  # For nested anonymous object types

    def __str__(self) -> str:
        if self.fields is not None:
            fields_str = ", ".join(f"{k}: {v}" for k, v in self.fields.items())
            return f"{{{fields_str}}}"
        if not self.type_args:
            return self.name
        args_str = ", ".join(str(a) for a in self.type_args)
        return f"{self.name}[{args_str}]"

    def __repr__(self) -> str:
        if self.fields is not None:
            return f"TypeSpec(fields={self.fields!r})"
        if not self.type_args:
            return f"TypeSpec({self.name!r})"
        return f"TypeSpec({self.name!r}, {self.type_args!r})"

    def to_dict(self) -> Dict[str, Any]:
        if self.fields is not None:
            return {
                "kind": "object",
                "fields": {k: v.to_dict() for k, v in self.fields.items()},
            }
        return {
            "kind": "type",
            "name": self.name,
            "type_args": [a.to_dict() for a in self.type_args],
            "repr": str(self),
        }

    def to_json_schema(self) -> Dict[str, Any]:
        """Converts this DSL type spec to OpenAPI / Gemini JSON Schema."""
        if self.fields is not None:
            props = {k: v.to_json_schema() for k, v in self.fields.items()}
            return {
                "type": "object",
                "properties": props,
                "required": list(props.keys()),
            }

        primitive_map = {
            "int": {"type": "integer"},
            "integer": {"type": "integer"},
            "float": {"type": "number"},
            "number": {"type": "number"},
            "str": {"type": "string"},
            "string": {"type": "string"},
            "bool": {"type": "boolean"},
            "boolean": {"type": "boolean"},
        }

        lower = self.name.lower()
        if lower in ("list", "array"):
            item_schema = self.type_args[0].to_json_schema() if self.type_args else {}
            return {"type": "array", "items": item_schema}
        if lower in ("dict", "map"):
            value_schema = self.type_args[1].to_json_schema() if len(self.type_args) > 1 else {}
            return {"type": "object", "additionalProperties": value_schema}
        return primitive_map.get(lower, {"type": "string", "description": self.name})


@dataclass
class GenerateBlock:
    """AST node for the 'generate [as TargetClass] { ... }' configuration."""
    target_class: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    schema: Dict[str, TypeSpec] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

    def to_json_schema(self) -> Dict[str, Any]:
        """Generates standard JSON Schema for the structured output."""
        properties = {k: v.to_json_schema() for k, v in self.schema.items()}
        schema_dict: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
        }
        if self.target_class:
            schema_dict["title"] = self.target_class
        return schema_dict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_class": self.target_class,
            "model": self.model,
            "temperature": self.temperature,
            "schema": {k: v.to_dict() for k, v in self.schema.items()},
            "json_schema": self.to_json_schema(),
            "options": self.options,
        }


@dataclass
class AIPScriptAST:
    """Root AST Node for a .aip program file."""
    system_prompt: Optional[SystemPromptNode] = None
    user_prompt: Optional[UserPromptNode] = None
    generate: Optional[GenerateBlock] = None

    def all_variables(self) -> List[str]:
        """Returns all referenced variables across system and user prompts."""
        vars_set = set()
        ordered = []
        if self.system_prompt:
            for v in self.system_prompt.variables:
                if v not in vars_set:
                    vars_set.add(v)
                    ordered.append(v)
        if self.user_prompt:
            for v in self.user_prompt.variables:
                if v not in vars_set:
                    vars_set.add(v)
                    ordered.append(v)
        return ordered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_prompt": self.system_prompt.to_dict() if self.system_prompt else None,
            "user_prompt": self.user_prompt.to_dict() if self.user_prompt else None,
            "generate": self.generate.to_dict() if self.generate else None,
            "variables": self.all_variables(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# 3. Lark AST Transformer
# ---------------------------------------------------------------------------

class AIPTransformer(Transformer):
    """Transforms raw parse tree into structured AST nodes."""

    def var_ref(self, items):
        return VariableToken(name=str(items[0]))

    def TEXT_FRAGMENT(self, token):
        return TextToken(text=str(token))

    def prompt_content(self, items):
        # Merge adjacent TextToken instances for canonical representation
        merged: List[PromptToken] = []
        for it in items:
            if isinstance(it, TextToken):
                if merged and isinstance(merged[-1], TextToken):
                    merged[-1] = TextToken(text=merged[-1].text + it.text)
                else:
                    merged.append(it)
            else:
                merged.append(it)
        return merged

    def system_block(self, items):
        return ("system", SystemPromptNode(tokens=items[0]))

    def user_block(self, items):
        return ("user", UserPromptNode(tokens=items[0]))

    def string_val(self, items):
        raw = str(items[0])
        # strip enclosing quotes and resolve escaped characters
        return raw[1:-1].encode("utf-8").decode("unicode_escape")

    def number_val(self, items):
        val = str(items[0])
        return float(val) if ("." in val or "e" in val.lower()) else int(val)

    def bool_true(self, _):
        return True

    def bool_false(self, _):
        return False

    def type_spec_rule(self, items):
        name = str(items[0])
        args = [it for it in items[1:] if isinstance(it, TypeSpec)]
        return TypeSpec(name=name, type_args=args)

    def nested_schema_rule(self, items):
        fields = items[0] if items and isinstance(items[0], dict) else {}
        return TypeSpec(name="object", fields=fields)

    def schema_field(self, items):
        return (str(items[0]), items[1])

    def schema_fields(self, items):
        return dict(items)

    def schema_block(self, items):
        if items and isinstance(items[0], dict):
            return items[0]
        return {}

    def config_entry(self, items):
        return (str(items[0]), items[1])

    def config_entries(self, items):
        return list(items)

    def generate_block(self, items):
        target_class = None
        configs = []
        for it in items:
            if isinstance(it, Token) and it.type == "CNAME":
                target_class = str(it)
            elif isinstance(it, list):
                configs = it

        gen = GenerateBlock(target_class=target_class)
        for k, v in configs:
            if k == "model":
                gen.model = v
            elif k == "temperature":
                gen.temperature = float(v)
            elif k == "schema" and isinstance(v, dict):
                gen.schema = v
            else:
                gen.options[k] = v
        return ("generate", gen)

    def script(self, items):
        ast = AIPScriptAST()
        for kind, node in items:
            if kind == "system":
                ast.system_prompt = node
            elif kind == "user":
                ast.user_prompt = node
            elif kind == "generate":
                ast.generate = node
        return ast


# ---------------------------------------------------------------------------
# 4. High-Level Parser Interface
# ---------------------------------------------------------------------------

class AIPParser:
    """Reusable AIP parser instance."""

    def __init__(self):
        self._lark = Lark(AIP_GRAMMAR, parser="earley")
        self._transformer = AIPTransformer()

    def parse(self, text: str) -> AIPScriptAST:
        """Parses an .aip source string into an AIPScriptAST."""
        tree = self._lark.parse(text)
        return self._transformer.transform(tree)

    def parse_file(self, filepath: str) -> AIPScriptAST:
        """Reads and parses an .aip file from disk."""
        with open(filepath, "r", encoding="utf-8") as f:
            return self.parse(f.read())


def parse_aip(source_code: str) -> AIPScriptAST:
    """Convenience helper to parse .aip source string."""
    return AIPParser().parse(source_code)


# ---------------------------------------------------------------------------
# 5. CLI and Verification Test Suite
# ---------------------------------------------------------------------------

SAMPLE_AIP = """system:
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

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        # Read from stdin and output JSON AST
        content = sys.stdin.read()
        try:
            ast = parse_aip(content)
            print(ast.to_json())
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)
        return

    print("=" * 70)
    print("AIP (AI Scripting DSL) Compiler & Parser - Test Suite")
    print("=" * 70)
    print("\n[1] Input Source (.aip):")
    print("-" * 50)
    print(SAMPLE_AIP.strip())
    print("-" * 50)

    # 1. Parse
    parser = AIPParser()
    ast = parser.parse(SAMPLE_AIP)

    print("\n[2] Abstract Syntax Tree (AST) Breakdown:")
    print("-" * 50)

    # System Prompt AST
    print("A. System Prompt Node:")
    print(f"   Tokens ({len(ast.system_prompt.tokens)}):")
    for tok in ast.system_prompt.tokens:
        print(f"     - {tok}")
    print(f"   Detected Variables: {ast.system_prompt.variables}")
    print(f"   Clean Text:\n     {repr(ast.system_prompt.raw_template.strip())}")

    # User Prompt AST
    print("\nB. User Prompt Node:")
    print(f"   Tokens ({len(ast.user_prompt.tokens)}):")
    for tok in ast.user_prompt.tokens:
        print(f"     - {tok}")
    print(f"   Detected Variables: {ast.user_prompt.variables}")
    print(f"   Raw Template:\n     {repr(ast.user_prompt.raw_template.strip())}")

    # Variable Interpolation Test
    test_context = {
        "name": "Bipin",
        "text": "The solar system contains eight planets orbiting the sun."
    }
    rendered_user = ast.user_prompt.render(test_context)
    print(f"\n   Interpolated with {test_context}:")
    print("   " + "\n   ".join(rendered_user.strip().splitlines()))

    # Generate Block AST
    print("\nC. Generate Block:")
    print(f"   Target Class: {ast.generate.target_class}")
    print(f"   Model:        {ast.generate.model}")
    print(f"   Temperature:  {ast.generate.temperature}")
    print("   Typed Schema Dictionary:")
    for field_name, type_spec in ast.generate.schema.items():
        print(f"     - {field_name}: {type_spec} (Internal AST: {type_spec!r})")

    # JSON Schema Generation
    print("\n[3] Generated Structured Output JSON Schema (OpenAPI / Gemini compliant):")
    print("-" * 50)
    print(json.dumps(ast.generate.to_json_schema(), indent=2))

    # Assertions
    assert ast.system_prompt is not None, "System prompt should be parsed"
    assert ast.user_prompt is not None, "User prompt should be parsed"
    assert ast.user_prompt.variables == ["name", "text"], f"Expected ['name', 'text'], got {ast.user_prompt.variables}"
    assert ast.generate.target_class == "AnalysisResult", "Target class mismatch"
    assert ast.generate.model == "gemini-2.0-flash", "Model mismatch"
    assert ast.generate.temperature == 0.2, "Temperature mismatch"
    assert "score" in ast.generate.schema and ast.generate.schema["score"].name == "int"
    assert "passed" in ast.generate.schema and ast.generate.schema["passed"].name == "bool"
    assert "notes" in ast.generate.schema and ast.generate.schema["notes"].name == "list"
    assert ast.generate.schema["notes"].type_args[0].name == "string"

    print("\n" + "=" * 70)
    print("ALL ASSERTIONS PASSED! Parser and AST separation verified successfully.")
    print("=" * 70)

if __name__ == "__main__":
    main()
