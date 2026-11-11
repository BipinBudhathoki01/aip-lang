# Changelog

## Unreleased

- Add a complete invoice extraction example with synthetic input, a hand-authored reference result, and Python/PHP/Laravel instructions.
- Add a shared browser/Python parser corpus and replace regex-only configuration extraction with complete parsing.
- Report source line/column diagnostics and reject unknown schema types, incorrect generic arity, and non-string dictionary keys.
- Preserve Unicode configuration strings and treat inline section markers as prompt prose.

### Compatibility notes

- Missing credentials no longer select fixtures. Use CLI `--mock`, Python `mock=True`, or an explicitly supplied test client for offline execution. CLI fixtures are now schema-shaped rather than examiner-specific, and mock mode is labeled on stderr.
- Section declarations must start on their own line. Prompt section names and colons must stay together. Malformed line-leading `generate as` declarations produce errors instead of becoming prompt text.
- Previously accepted unsupported schema types and bare/unparameterized collections now produce diagnostics.
