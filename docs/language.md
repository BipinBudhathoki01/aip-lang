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

Section headers are reserved syntax. The current parser can interpret `system:`, `user:`, or a `generate {` declaration inside prompt text as a section boundary. Avoid those literal patterns until escaping is supported.

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

The supported subset does not include optional fields, enums, unions, arbitrary constraints, or full JSON Schema. Unknown types currently fall back to strings; this behavior is tracked for improvement. Use only the documented types.

## Validation and retries

Add `provider: "openai"` or `provider: "anthropic"` inside the generate block to change providers. Gemini remains the default. `max_tokens` sets a positive output token limit. See [providers](providers.md) for credentials, model defaults, and differences in provider-side output formatting. New providers omit temperature unless explicitly supplied; some models reject that option.

The runtime validates JSON using generated Pydantic models. Generated PHP validates the supported schema subset before constructing the result DTO. Failed responses can be sent back with correction feedback up to the configured retry count. Provider errors and exhausted validation retries are reported to the caller. Structure validation does not check factual accuracy.
