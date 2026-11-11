"""JSON stdin bridge for the local playground; source is parsed, never executed."""
import json
import sys
from aip_parser import parse_aip
from aip_runtime import MockGeminiClient, interpolate_ast_prompts, run_aip


def sample_value(spec):
    if spec.fields is not None:
        return {k: sample_value(v) for k, v in spec.fields.items()}
    name = spec.name.lower()
    if name in ("list", "array"):
        return []
    if name in ("dict", "map"):
        return {}
    if name in ("int", "integer"):
        return 0
    if name in ("float", "number"):
        return 0.0
    if name in ("bool", "boolean"):
        return False
    return "Mock value"


def process(payload):
    ast = parse_aip(payload["code"])
    if payload.get("action") == "parse":
        return ast.to_dict()
    if not ast.generate or not ast.generate.schema:
        raise ValueError("A generate block with a schema is required to run.")
    variables = payload.get("variables", {})
    system, user = interpolate_ast_prompts(ast, variables)
    sample = {k: sample_value(v) for k, v in ast.generate.schema.items()}
    result = run_aip(ast, variables, client=MockGeminiClient([json.dumps(sample)]))
    return {"mode": "mock", "system": system, "user": user, "result": result}


if __name__ == "__main__":
    try:
        print(json.dumps(process(json.load(sys.stdin)), ensure_ascii=True))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
