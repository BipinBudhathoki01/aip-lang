# Prompts with a contract.

AIP Lang puts instructions, variables, model settings, and a typed output schema in one version-controlled text file. Compile to Python or PHP, or execute through the Python CLI.

**Early preview · MIT licensed · Contributions welcome**

[Get started](quickstart.md) · [Open playground](https://bipinbudhathoki01.github.io/aip-lang/playground/) · [View source](https://github.com/BipinBudhathoki01/aip-lang)

```text
user:
    Summarize this message: {{ $message }}
generate as Ticket {
    model: "gemini-3.8-flash",
    schema: { summary: string, urgent: bool, tags: list[string] }
}
```

## One file to review

Keep prompts and output expectations together. Review them in pull requests alongside your application code.

## Native integration

Generate a Python module with Pydantic models or a PHP class that calls Gemini directly. PHP does not need Python at runtime.

## Validate, then return

Validate generated JSON and retry a bounded number of times when syntax or supported schema checks fail. Exhausted retries raise an error. Validation does not guarantee correct facts.

## Built in the open

Start with a local mock run without an API key. Help improve diagnostics, parser parity, examples, and integration tests. See the [contribution guide](contributing.md).

## Status and boundaries

Gemini is the only live provider. Optional fields, enums, unions, streaming, and async execution are planned rather than implemented. The browser parser is a preview; Python is authoritative. This documentation site and the hosted playground are static. Run the local server for Python execution.

## About the extension

New examples use `.aiprompt`. Existing `.aip` files remain supported. `.aip` also identifies Adobe Illustrator plug-ins, so the longer suffix helps distinguish readable prompt contracts from binary plug-ins. Neither extension is claimed to be globally unique. The CLI accepts UTF-8 source regardless of filename suffix.
