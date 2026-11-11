"""JSON stdin bridge for the local playground; source is parsed, never executed."""
import json
import sys
from aip_parser import parse_aip
from aip_runtime import interpolate_ast_prompts, run_aip


def process(payload):
    ast = parse_aip(payload["code"])
    if payload.get("action") == "parse":
        return ast.to_dict()
    if not ast.generate or not ast.generate.schema:
        raise ValueError("A generate block with a schema is required to run.")
    variables = payload.get("variables", {})
    system, user = interpolate_ast_prompts(ast, variables)
    result = run_aip(ast, variables, mock=True)
    return {"mode": "mock", "system": system, "user": user, "result": result}


if __name__ == "__main__":
    try:
        print(json.dumps(process(json.load(sys.stdin)), ensure_ascii=True))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
