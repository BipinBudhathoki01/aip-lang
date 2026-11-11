# Roadmap

This is an early preview, not a delivery schedule. Please discuss major additions in an issue first.

## Current focus

- [ ] Expand generated Python/PHP behavior tests, especially nested schemas and escaping.
- [x] Align documented browser/Python parsing cases with a shared fixture suite.
- [x] Add line/column diagnostics and reject unsupported schema types.
- [ ] Add practical Laravel and Django integration examples.
- [x] Require explicit schema-shaped mock execution.

## Next

- [ ] Optional fields, enums, and schema constraints with cross-target parity.
- [x] Provider abstraction with OpenAI and Anthropic Claude in the runtime and generated Python/PHP.
- [x] Groq and local Ollama in the runtime and generated Python/PHP.
- [ ] Retry cost/latency reporting and configurable timeouts.
- [ ] Editor syntax highlighting for `.aiprompt` and legacy `.aip`.
- [ ] Publish a verified Python package after packaging checks.

## Later, after user feedback

- [ ] Async execution and streaming.
- [ ] Prompt regression evaluations and version comparison.
- [ ] Framework adapters informed by real integrations.

Suggest a feature by describing a concrete workflow and what AIP would make easier.

## Public release and adoption tasks

- [ ] Live provider and generated-executor verification (#8).
- [ ] Fresh installation checks on Windows, Linux, and macOS (#9).
- [ ] Verified versioned preview/Python package release (#10).
- [ ] VS Code syntax highlighting (#11).
- [ ] Five-developer feedback round and continuing integrations (#12).
- [ ] Two-minute demonstration and launch guide (#13).
