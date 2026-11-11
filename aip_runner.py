#!/usr/bin/env python3
"""
AIP Runner CLI: Command-Line Interface for executing .aip DSL scripts.

Usage:
    python aip_runner.py run <path_to_file.aip> --data '{"name": "John", "text": "Sample essay"}'
    python aip_runner.py run <path_to_file.aip> --file data.json

STDOUT:
    Outputs ONLY the final validated JSON (can be directly consumed by PHP shell_exec(),
    Node.js exec(), or Bash jq).

STDERR:
    Diagnostic messages, auto-healing logs, and error traces.
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any

from aip_parser import parse_aip
from aip_lang.providers import provider_settings
from aip_runtime import run_aip, AIPExecutionError, MockGeminiClient


def load_variables(args: argparse.Namespace) -> Dict[str, Any]:
    """Loads variable dictionary from --data string or --file path."""
    variables: Dict[str, Any] = {}

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"[AIP Error] Variables file not found: {args.file}\n")
            sys.exit(1)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    sys.stderr.write(f"[AIP Error] Expected JSON object in {args.file}, got {type(loaded).__name__}\n")
                    sys.exit(1)
                variables.update(loaded)
        except json.JSONDecodeError as err:
            sys.stderr.write(f"[AIP Error] Failed to parse JSON file {args.file}: {err}\n")
            sys.exit(1)

    if args.data:
        try:
            loaded = json.loads(args.data)
            if not isinstance(loaded, dict):
                sys.stderr.write(f"[AIP Error] --data must be a JSON object, got {type(loaded).__name__}\n")
                sys.exit(1)
            variables.update(loaded)
        except json.JSONDecodeError as err:
            sys.stderr.write(f"[AIP Error] Invalid JSON string passed to --data: {err}\n")
            sys.exit(1)

    return variables


def run_command(args: argparse.Namespace) -> None:
    """Executes the 'run' subcommand."""
    # 1. Read .aip script file
    script_path = Path(args.script_path)
    if not script_path.exists():
        sys.stderr.write(f"[AIP Error] Script file not found: {args.script_path}\n")
        sys.exit(1)

    if not script_path.is_file():
        sys.stderr.write(f"[AIP Error] Path is not a file: {args.script_path}\n")
        sys.exit(1)

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
    except Exception as err:
        sys.stderr.write(f"[AIP Error] Failed to read script {args.script_path}: {err}\n")
        sys.exit(1)

    # 2. Parse into AST
    try:
        ast = parse_aip(script_content)
    except Exception as parse_err:
        sys.stderr.write(f"[AIP Syntax Error] Failed to parse {args.script_path}:\n{parse_err}\n")
        sys.exit(1)

    # 3. Load variables
    variables = load_variables(args)

    # 4. Check API Key
    try:
        provider, key_name, *_ = provider_settings(ast)
    except ValueError as error:
        sys.stderr.write(f"[AIP Error] {error}\n")
        sys.exit(1)
    api_key = os.environ.get(key_name)
    client = None
    if args.mock:
        client = MockGeminiClient()
    elif provider == "gemini" and (not api_key or api_key.startswith("MY_")):
        # If no key set, fallback to mock with warning to stderr
        sys.stderr.write("[AIP Warning] GEMINI_API_KEY not found or placeholder in environment. Running with deterministic mock client.\n")
        client = MockGeminiClient()

    # 5. Execute with auto-healing loop
    try:
        result = run_aip(
            ast=ast,
            variables=variables,
            client=client,
            max_retries=args.retries,
            verbose=args.verbose,
        )
    except KeyError as key_err:
        sys.stderr.write(f"[AIP Variable Error] {key_err}\n")
        sys.exit(1)
    except AIPExecutionError as exec_err:
        sys.stderr.write(f"[AIP Execution Error] {exec_err}\n")
        if exec_err.errors:
            sys.stderr.write("Detailed failure history:\n")
            for line in exec_err.errors:
                sys.stderr.write(f"  {line}\n")
        sys.exit(1)
    except Exception as unhandled_err:
        sys.stderr.write(f"[AIP Unexpected Error] {unhandled_err}\n")
        sys.exit(1)

    # 6. Output ONLY validated JSON to STDOUT
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


def compile_command(args: argparse.Namespace) -> None:
    """Executes the 'compile' subcommand."""
    from aip_lang.codegen_python import generate_python_code
    from aip_lang.codegen_php import generate_php_code

    script_path = Path(args.script_path)
    if not script_path.exists():
        sys.stderr.write(f"[AIP Error] Script file not found: {args.script_path}\n")
        sys.exit(1)

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            ast = parse_aip(f.read())
    except Exception as err:
        sys.stderr.write(f"[AIP Syntax Error] Failed to parse {args.script_path}: {err}\n")
        sys.exit(1)

    target = args.target.lower()
    base_name = ''.join(part[:1].upper() + part[1:] for part in re.split(r'[^A-Za-z0-9_]+', script_path.stem) if part)
    if not base_name or base_name[0].isdigit():
        base_name = 'Prompt' + base_name

    if target in ("py", "python"):
        code = generate_python_code(ast, module_name=script_path.stem)
        default_out = f"generated_{script_path.stem}.py"
    elif target in ("php", "laravel"):
        code = generate_php_code(ast, class_name=f"{base_name}Aip", namespace=args.namespace or "App\\AI")
        default_out = f"{base_name}Aip.php"
    else:
        sys.stderr.write(f"[AIP Error] Unknown target language: '{args.target}'. Supported targets: python, php\n")
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(code)
        sys.stderr.write(f"[AIP] Compiled {script_path} -> {out_path} ({len(code.splitlines())} lines)\n")
    else:
        print(code)


def schema_command(args: argparse.Namespace) -> None:
    """Outputs the JSON Schema for the .aip file."""
    script_path = Path(args.script_path)
    if not script_path.exists():
        sys.stderr.write(f"[AIP Error] Script file not found: {args.script_path}\n")
        sys.exit(1)

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            ast = parse_aip(f.read())
    except Exception as err:
        sys.stderr.write(f"[AIP Syntax Error] Failed to parse: {err}\n")
        sys.exit(1)

    if not ast.generate or not ast.generate.schema:
        sys.stderr.write("[AIP Error] No schema block found in generate declaration.\n")
        sys.exit(1)

    print(json.dumps(ast.generate.to_json_schema(), indent=2))


def check_command(args: argparse.Namespace) -> None:
    """Validates syntax and variable declarations without executing."""
    script_path = Path(args.script_path)
    if not script_path.exists():
        sys.stderr.write(f"[AIP Error] Script file not found: {args.script_path}\n")
        sys.exit(1)

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            ast = parse_aip(f.read())
    except Exception as err:
        sys.stderr.write(f"[AIP Syntax Error] {err}\n")
        sys.exit(1)

    vars_found = ast.all_variables()
    model = ast.generate.model if ast.generate else "default"
    target = ast.generate.target_class if ast.generate else "None"
    fields = list(ast.generate.schema.keys()) if ast.generate else []

    sys.stderr.write(f"[AIP Check] Syntax valid: {args.script_path}\n")
    sys.stderr.write(f"  - Target Class: {target}\n")
    sys.stderr.write(f"  - Model: {model}\n")
    sys.stderr.write(f"  - Variables ({len(vars_found)}): {', '.join(f'${v}' for v in vars_found)}\n")
    sys.stderr.write(f"  - Schema Fields ({len(fields)}): {', '.join(fields)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aip",
        description="AIP: The Declarative AI Scripting Language & Code Generator.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Subcommand: run
    run_parser = subparsers.add_parser("run", help="Execute an .aip script file")
    run_parser.add_argument("script_path", help="Path to the .aip script file")
    run_parser.add_argument("--data", "-d", type=str, help="Inline JSON string providing template variables")
    run_parser.add_argument("--file", "-f", type=str, help="Path to a JSON file containing template variables")
    run_parser.add_argument("--retries", type=int, default=2, help="Max auto-healing retries (default: 2)")
    run_parser.add_argument("--pretty", action="store_true", help="Pretty-print the output JSON")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Write runtime auto-healing logs to stderr")
    run_parser.add_argument("--mock", action="store_true", help="Force execution using mock Gemini client")

    # 2. Subcommand: compile
    compile_parser = subparsers.add_parser("compile", help="Compile .aip script into native Python or PHP code")
    compile_parser.add_argument("script_path", help="Path to the .aip script file")
    compile_parser.add_argument("--target", "-t", choices=["python", "php", "py", "laravel"], default="python", help="Target language (python or php)")
    compile_parser.add_argument("--out", "-o", type=str, help="Output destination file path")
    compile_parser.add_argument("--namespace", type=str, default="App\\AI", help="PHP namespace (default: App\\AI)")

    # 3. Subcommand: schema
    schema_parser = subparsers.add_parser("schema", help="Output OpenAPI / Gemini JSON Schema")
    schema_parser.add_argument("script_path", help="Path to the .aip script file")

    # 4. Subcommand: check
    check_parser = subparsers.add_parser("check", help="Lint and validate .aip script syntax and parameters")
    check_parser.add_argument("script_path", help="Path to the .aip script file")

    args = parser.parse_args()
    if args.command == "run":
        run_command(args)
    elif args.command == "compile":
        compile_command(args)
    elif args.command == "schema":
        schema_command(args)
    elif args.command == "check":
        check_command(args)


if __name__ == "__main__":
    main()
