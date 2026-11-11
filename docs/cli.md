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

`--mock` uses the built-in examiner fixture; use the local playground for schema-shaped fixtures with arbitrary schemas. Without a configured Gemini API key the CLI currently falls back to that fixture and warns on stderr. OpenAI, Anthropic, and Groq instead require their own credentials. Ollama requires a reachable server with the selected model installed, without an API key. See [providers](providers.md).

## Compile

```bash
aip compile examples/examiner.aiprompt --target python --out generated/examiner.py
aip compile examples/examiner.aiprompt --target php --out generated/ExaminerAip.php
```

Without `--out`, generated source is written to stdout. PHP supports `--namespace App\AI`. Generated files are build outputs; regenerate them after editing the prompt.

Python outputs need Pydantic, plus google-genai for Gemini execution. OpenAI, Anthropic, Groq, and Ollama use HTTP(S) directly. PHP outputs need PHP 8.1+, JSON, and cURL. Compiling does not call a provider.
