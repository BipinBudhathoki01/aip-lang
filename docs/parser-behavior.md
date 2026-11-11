# Parsing and diagnostics

The browser preview and Python parser run the same shared fixture corpus from `tests/fixtures/parser_cases.json`. Python remains authoritative for execution and compilation. The corpus compares variable order and JSON Schema, and selected cases also compare model settings and prompt text.

## Supported and tested cases

The corpus covers nested objects, nested lists, dictionaries, primitive aliases, empty objects, trailing commas, signed/exponent numbers, escaped strings, Unicode configuration strings, repeated variables, and reserved section markers. Invalid cases cover malformed declarations, unclosed blocks, missing commas/colons, invalid placeholders, unsupported types, wrong generic arity, and invalid configuration value types.

Browser configuration parsing now reads complete declarations rather than extracting selected values using regular expressions. Invalid blocks return a diagnostic rather than an apparently valid empty schema. `int`, `float`, `bool`, and `string` aliases have no type arguments; `list[T]` requires one; `dict[string, T]` requires two. Unknown types and non-string dictionary keys are rejected.

## Section boundaries

Put each `system:`, `user:`, and `generate` declaration at the start of its own line, optionally indented. Keep prompt section names and their colon on the same line. A named generation declaration must use `generate as ClassName { ... }`.

Inline words such as `Explain system: text and user: text` remain prompt text. A real section header at the beginning of a line starts a section, even inside what you intended as prompt prose. Literal line-leading headers do not yet have an escape syntax; rephrase or keep them inline. `generate as` at the beginning of a line is reserved for a declaration and malformed versions produce an error.

## Error messages

CLI `check`, `schema`, `compile`, and `run` report syntax failures to stderr with a line, column, source excerpt, and caret. They exit with code 1 and leave stdout empty. Semantic type errors point to the associated field. Browser diagnostics use the same style; error wording can differ between implementations.

The shared corpus is regression coverage rather than a proof that every possible input behaves identically. Raw prompt whitespace/token segmentation and diagnostic wording are not compared byte for byte. Provider availability, credentials, and model-specific settings are checked during execution rather than established by parsing. Please report mismatches with a minimal example and add a shared fixture with the fix.
