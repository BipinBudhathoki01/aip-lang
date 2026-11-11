"""
Python Code Generator for AIP scripts.
Compiles an .aip AST into a standalone, typed Python module with Pydantic schemas
and built-in auto-healing logic.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List
from aip_parser import AIPScriptAST, TypeSpec, VariableToken, TextToken


def _type_spec_to_py_type(spec: TypeSpec, models=None, prefix="Nested") -> str:
    if spec.fields is not None:
        if models is None:
            raise ValueError("Nested types require a model registry")
        fields = [f"    {name}: {_type_spec_to_py_type(child, models, prefix + '_' + name)}" for name, child in spec.fields.items()]
        models.append(f"class {prefix}(BaseModel):\n    model_config = ConfigDict(strict=True, extra='forbid')\n" + ('\n'.join(fields) or '    pass'))
        return prefix
    primitive_map = {
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "str": "str",
        "string": "str",
        "bool": "bool",
        "boolean": "bool",
    }
    lower = spec.name.lower()
    if lower in ("list", "array"):
        inner = _type_spec_to_py_type(spec.type_args[0], models, prefix + '_Item') if spec.type_args else "Any"
        return f"List[{inner}]"
    if lower in ("dict", "map"):
        k = _type_spec_to_py_type(spec.type_args[0], models, prefix + '_Key') if len(spec.type_args) > 0 else "str"
        v = _type_spec_to_py_type(spec.type_args[1], models, prefix + '_Value') if len(spec.type_args) > 1 else "Any"
        return f"Dict[{k}, {v}]"
    return primitive_map.get(lower, "str")


def generate_python_code(ast: AIPScriptAST, module_name: str = "generated_aip") -> str:
    """Compiles an AIPScriptAST into an independent Python module."""
    target_class = ast.generate.target_class if ast.generate and ast.generate.target_class else "AipOutput"
    model_name = ast.generate.model if ast.generate and ast.generate.model else "gemini-3.8-flash"
    temperature = ast.generate.temperature if ast.generate and ast.generate.temperature is not None else 0.2

    # Map deprecated aliases

    # Extract schema fields
    schema_fields = ast.generate.schema if ast.generate else {}
    variables = ast.all_variables()

    # Reconstruct prompt templates using Python f-strings
    def tokens_to_fstring(tokens) -> str:
        parts = []
        for t in tokens:
            if isinstance(t, VariableToken):
                parts.append(f"{{{t.name}}}")
            elif isinstance(t, TextToken):
                # Escape curly braces
                txt = t.text.replace("\\", "\\\\").replace('"', '\\"').replace("{", "{{").replace("}", "}}")
                parts.append(txt)
            else:
                parts.append(str(t))
        return "".join(parts).strip()

    system_fstring = tokens_to_fstring(ast.system_prompt.tokens) if ast.system_prompt else ""
    user_fstring = tokens_to_fstring(ast.user_prompt.tokens) if ast.user_prompt else ""

    pydantic_fields = []
    nested_models = []
    for f_name, f_spec in schema_fields.items():
        py_type = _type_spec_to_py_type(f_spec, nested_models, target_class + '_' + f_name)
        pydantic_fields.append(f"    {f_name}: {py_type}")

    fields_code = "\n".join(pydantic_fields) if pydantic_fields else "    pass"
    nested_code = "\n\n".join(nested_models)
    params_code = ", ".join([f"{v}: str" for v in variables])
    if params_code:
        params_code += ", "

    code = f'''# Generated automatically by AIP Compiler (aip-lang)
# DO NOT EDIT MANUALLY. Re-run `aip compile` to regenerate.

from __future__ import annotations
import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, ValidationError

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


{nested_code}

class {target_class}(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
{fields_code}


def run_{target_class.lower()}(
    {params_code}api_key: Optional[str] = None,
    max_retries: int = 2
) -> {target_class}:
    """
    Executes prompt with typed output schema {target_class} and auto-healing retries.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key or not HAS_GENAI:
        raise RuntimeError("GEMINI_API_KEY is required and google-genai package must be installed.")

    client = genai.Client(api_key=key)

    # Render prompts
    system_instruction = f"""\\
{system_fstring}
""".strip()

    user_prompt = f"""\\
{user_fstring}
""".strip()

    config = genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema={target_class},
        temperature={temperature},
    )

    current_prompt = user_prompt
    history = []

    for attempt in range(max_retries + 1):
        full_contents = []
        for turn in history:
            full_contents.append(f"{{turn['role'].upper()}}: {{turn['text']}}")
        full_contents.append(current_prompt)

        response = client.models.generate_content(
            model="{model_name}",
            contents="\\n\\n".join(full_contents),
            config=config,
        )
        raw_text = response.text or ""

        try:
            parsed = json.loads(raw_text)
            return {target_class}.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as err:
            if attempt == max_retries:
                raise RuntimeError(f"Failed to obtain valid {target_class} output after {{max_retries + 1}} attempts: {{err}}")

            history.append({{"role": "user", "text": current_prompt}})
            history.append({{"role": "model", "text": raw_text}})
            current_prompt = (
                f"CORRECTION REQUIRED: Your response failed schema validation with error:\\n{{err}}\\n\\n"
                f"Please fix the payload and return strictly conforming JSON."
            )

    raise RuntimeError("Unexpected end of retry loop.")
'''
    return code
