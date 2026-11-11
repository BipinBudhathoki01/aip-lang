# Language reference

An AIP file is UTF-8 text. Prefer `.aiprompt`; `.aip` remains compatible.

## Prompt sections

```text
system:
    You extract structured data.
user:
    Read the message from {{ $name }}: {{ $message }}
```

Variables use `{{ $identifier }}`. The runtime requires every referenced variable before calling the model. Prompt values are inserted as text, not evaluated as Python or PHP. User-provided text can still influence model behavior; this syntax does not prevent prompt injection.

Section headers are reserved at the beginning of a line, optionally indented. Put each declaration on its own line and keep `system:` / `user:` names and colons together. Inline mentions such as `Explain system: text` remain prose. Literal line-leading headers still have no escape syntax. See [parser behavior](parser-behavior.md).

## Generation and schema

```text
generate as MessageResult {
    model: "gemini-3.8-flash",
    temperature: 0.2,
    schema: {
        summary: string,
        count: int,
        confidence: float,
        urgent: bool,
        tags: list[string],
        author: { name: string, verified: bool },
        scores: dict[string, int]
    }
}
```

Primitive aliases: `str`/`string`, `int`/`integer`, `float`/`number`, `bool`/`boolean`. Collections: `list[T]`/`array[T]`, `dict[string, T]`/`map[string, T]`. Anonymous nested objects are supported. All declared fields are required. JSON object keys are strings.

The supported subset does not include optional fields, enums, unions, arbitrary constraints, or full JSON Schema. Unknown types, incorrect generic arity, and non-string dictionary keys are rejected with a source diagnostic. Use only the documented types.

## Validation and retries

Add `provider: "openai"`, `provider: "anthropic"`, `provider: "groq"`, or `provider: "ollama"` inside the generate block to change providers. Gemini remains the default. `max_tokens` sets a positive output token limit. See [providers](providers.md) for credentials, model defaults, and differences in provider-side output formatting. New providers omit temperature unless explicitly supplied; some models reject that option.

The runtime validates JSON using generated Pydantic models. Generated PHP validates the supported schema subset before constructing the result DTO. Failed responses can be sent back with correction feedback up to the configured retry count. Provider errors and exhausted validation retries are reported to the caller. Structure validation does not check factual accuracy.
