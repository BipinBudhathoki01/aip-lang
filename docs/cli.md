# CLI reference

Install the project before using the `aip` command. `aip-runner` is an alias. Filenames can use `.aiprompt` or legacy `.aip`.

## Check

```bash
aip check examples/examiner.aiprompt
```

Parses source and reports variables, model, and schema fields. This is a syntax check, not a provider availability check or a complete semantic linter.

## Schema

```bash
aip schema examples/examiner.aiprompt
```

Writes the supported JSON Schema representation to stdout.

## Run

```bash
aip run examples/examiner.aiprompt --file examples/data.json --mock --pretty
```

Use `--data` for an inline JSON object or `--file` for a JSON file. Inline values override file values. `--retries 2` allows one initial attempt plus two correction attempts. `--verbose` sends diagnostics to stderr. Successful stdout is JSON.

`--mock` explicitly returns schema-shaped synthetic fixtures for any supported schema and labels the mode on stderr. It never contacts a model. Missing cloud credentials without mock mode produce an error and no success payload. Ollama needs a reachable server and installed model instead of an API key. In Python, use `run_aip(source, variables, mock=True)` or pass an explicit test client. See [providers](providers.md) and the [invoice example](invoice-example.md).

## Compile

```bash
aip compile examples/examiner.aiprompt --target python --out generated/examiner.py
aip compile examples/examiner.aiprompt --target php --out generated/ExaminerAip.php
```

Without `--out`, generated source is written to stdout. PHP supports `--namespace App\AI`. Generated files are build outputs; regenerate them after editing the prompt.

Python outputs need Pydantic, plus google-genai for Gemini execution. OpenAI, Anthropic, Groq, and Ollama use HTTP(S) directly. PHP outputs need PHP 8.1+, JSON, and cURL. Compiling does not call a provider.
