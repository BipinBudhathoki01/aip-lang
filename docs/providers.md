# Model providers

AIP supports Gemini, OpenAI models (the API behind ChatGPT), Anthropic Claude, Groq, and local Ollama servers. Set `provider` inside the generate block. Existing files without a provider keep using Gemini; a model name alone does not switch providers.

| Provider | Setting | Environment variable | Default model |
| --- | --- | --- | --- |
| Google Gemini | `"gemini"` | `GEMINI_API_KEY` | `gemini-3.8-flash` |
| OpenAI | `"openai"` | `OPENAI_API_KEY` | `gpt-5-mini` |
| Anthropic Claude | `"anthropic"` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| Groq | `"groq"` | `GROQ_API_KEY` | `openai/gpt-oss-20b` |
| Ollama | `"ollama"` | None for local use; optional `OLLAMA_BASE_URL` | `llama3.2` |

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

## Groq

```text
user:
    Summarize this message: {{ $message }}
generate as Summary {
    provider: "groq",
    model: "openai/gpt-oss-20b",
    max_tokens: 1024,
    schema: { summary: string, urgent: bool }
}
```

Set `GROQ_API_KEY` in your shell, then run:

```bash
aip run examples/groq-summary.aiprompt --file examples/summary-data.json
```

Groq uses its [Chat Completions API](https://console.groq.com/docs/api-reference) with JSON Object Mode, schema instructions, and AIP's local validation/retries. `max_tokens` maps to `max_completion_tokens`. JSON Object Mode does not enforce the schema remotely; local validation remains required. No Groq SDK is needed.

## Ollama

Install and start [Ollama](https://docs.ollama.com/quickstart), then download the model you want to run yourself:

```bash
ollama pull llama3.2
aip run examples/ollama-summary.aiprompt --file examples/summary-data.json
```

The default server is `http://127.0.0.1:11434`. No API key is required or sent by this adapter. AIP does not install Ollama, start its server, or download models automatically. Choose a model your machine can run.

```text
user:
    Summarize this message: {{ $message }}
generate as Summary {
    provider: "ollama",
    model: "llama3.2",
    max_tokens: 1024,
    temperature: 0.2,
    schema: { summary: string, urgent: bool }
}
```

Ollama uses its [native chat API](https://docs.ollama.com/api/chat) with `stream: false` and the output schema in `format`, followed by AIP's local validation/retries. `max_tokens` maps to `options.num_predict`; temperature goes in `options.temperature`.

Set `OLLAMA_BASE_URL` in the runtime environment to override the server. For example, in PowerShell use `$env:OLLAMA_BASE_URL = 'http://localhost:11434'`. In containers, `127.0.0.1` refers to that container; use the reachable Ollama host. HTTP(S) base URLs may include a reverse-proxy path prefix but must not contain credentials, query parameters, or fragments. Changing this address changes where prompt data is sent. Authenticated or cloud Ollama endpoints are not implemented. Ollama cloud does not currently support the structured output mode used here.

## Settings and failures

`max_tokens` is a positive integer, defaulting to 4096. For OpenAI it maps to `max_output_tokens`, which includes reasoning tokens. Increase the limit when needed; truncated output is treated as an error rather than a valid result. For Anthropic it maps to `max_tokens`.

New providers omit `temperature` unless the prompt explicitly sets it. Some models reject temperature; leave it out for those models. Gemini retains its existing default of 0.2. Model IDs are passed through unchanged.

Missing OpenAI, Anthropic, or Groq keys fail clearly; they never fall back to another provider or a mock. Ollama requires a reachable local/server installation rather than a key; connection and missing-model errors fail clearly too. The existing Gemini missing-key fallback remains for compatibility and is tracked separately. Use `--mock` explicitly for an offline CLI fixture; that fixture is examiner-specific. The local playground synthesizes fixtures for arbitrary supported schemas and never calls a provider.

Runtime and generated Python/PHP executors support all five providers. OpenAI, Anthropic, Groq, and Ollama use HTTP(S) directly and need no additional Python SDK. Generated Python still requires Pydantic; Gemini execution additionally requires google-genai. Generated PHP requires cURL and JSON. HTTP adapters and generated PHP requests have a 30-second timeout, including Ollama model loading; pre-warm a slow local model if necessary. Refusals, empty outputs, provider failures, and truncation raise errors.

Support is verified with offline request/response fixtures, including generated-code execution. Paid live-provider calls are not part of the test suite. Azure OpenAI, Bedrock, streaming, multimodal input, and arbitrary compatible endpoints are not implemented.
