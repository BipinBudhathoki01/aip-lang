# Model providers

AIP supports Gemini, OpenAI models (the API behind ChatGPT), and Anthropic Claude. Set `provider` inside the generate block. Existing files without a provider keep using Gemini; a model name alone does not switch providers.

| Provider | Setting | Environment variable | Default model |
| --- | --- | --- | --- |
| Google Gemini | `"gemini"` | `GEMINI_API_KEY` | `gemini-3.8-flash` |
| OpenAI | `"openai"` | `OPENAI_API_KEY` | `gpt-5-mini` |
| Anthropic Claude | `"anthropic"` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |

Choose a model available to your API account. ChatGPT or Claude consumer subscriptions do not replace API credentials. Availability and billing depend on the provider.

## OpenAI

```text
user:
    Summarize this message: {{ $message }}
generate as Summary {
    provider: "openai",
    model: "gpt-5-mini",
    max_tokens: 8192,
    schema: { summary: string, urgent: bool }
}
```

In PowerShell set `$env:OPENAI_API_KEY = 'your-key'`. On macOS/Linux use `export OPENAI_API_KEY='your-key'`. Run the file with `aip run` and your variables, or compile it to Python or PHP using the same commands as Gemini.

OpenAI uses the [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create), a JSON Schema text format with provider-side strict mode disabled, and AIP's local strict validation plus correction retries. This avoids claiming that every AIP schema belongs to the provider's stricter schema subset. Requests set `store: false`.

## Anthropic Claude

```text
user:
    Summarize this message: {{ $message }}
generate as Summary {
    provider: "anthropic",
    model: "claude-sonnet-4-6",
    max_tokens: 4096,
    schema: { summary: string, urgent: bool }
}
```

Set `ANTHROPIC_API_KEY` in your shell. Claude uses the [Messages API](https://platform.claude.com/docs/en/api/messages/create). AIP includes the schema in the instructions, requests JSON text, then applies local strict validation and correction retries. This adapter does not enable Anthropic's native constrained output mode or force a tool call.

## Settings and failures

`max_tokens` is a positive integer, defaulting to 4096. For OpenAI it maps to `max_output_tokens`, which includes reasoning tokens. Increase the limit when needed; truncated output is treated as an error rather than a valid result. For Anthropic it maps to `max_tokens`.

New providers omit `temperature` unless the prompt explicitly sets it. Some models reject temperature; leave it out for those models. Gemini retains its existing default of 0.2. Model IDs are passed through unchanged.

Missing OpenAI or Anthropic keys fail clearly; they never fall back to another provider or a mock. The existing Gemini missing-key fallback remains for compatibility and is tracked separately. Use `--mock` explicitly for an offline CLI fixture; that fixture is examiner-specific. The local playground synthesizes fixtures for arbitrary supported schemas and never calls a provider.

Runtime and generated Python/PHP executors support all three providers. OpenAI and Anthropic use HTTPS directly and need no additional Python SDK. Generated Python still requires Pydantic; Gemini execution additionally requires google-genai. Generated PHP requires cURL and JSON. OpenAI/Anthropic HTTP requests and generated PHP requests have a 30-second timeout. Refusals, empty outputs, provider failures, and truncation raise errors.

Support is verified with offline request/response fixtures, including generated-code execution. Paid live-provider calls are not part of the test suite. Azure OpenAI, Bedrock, streaming, multimodal input, and arbitrary compatible endpoints are not implemented.
