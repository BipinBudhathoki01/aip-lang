# Contributing to AIP Lang

Thanks for helping build a small, dependable prompt contract language. Bug reports, documentation, examples, and code contributions are welcome.

## Set up

Fork the repository, clone your fork, and create a branch for your change. Install Python 3.10+, Node.js 22.12+, and optionally PHP 8.1+ for code-generation checks.

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
npm ci
npm run dev
```

No API key is needed for tests or the playground's mock run. Never commit credentials or private user inputs.

## Where to work

| Path | Purpose |
| --- | --- |
| `aip_parser.py` | Grammar, AST, and JSON Schema conversion |
| `aip_runtime.py` | Interpolation, validation, and bounded retries |
| `aip_lang/` | Native Python/PHP generators |
| `aip_runner.py` | CLI commands |
| `playground_runner.py`, `server.ts` | Local playground bridge |
| `src/` | React UI and browser parser |
| `tests/` | Authoritative Python regression tests |
| `docs/` | Documentation source |

Add Python tests under `tests/`.

## Before a pull request

```bash
python -m unittest discover -s tests -v
npm test
npm run lint
npm run build
```

For compiler changes, include a regression case that compiles a prompt and checks the generated program's behavior. PHP tests skip locally when PHP is unavailable; CI installs it. Do not commit generated output, virtual environments, dependency folders, or secrets.

Keep changes focused and explain the problem, resulting behavior, and validation. Open an issue before large syntax or architecture changes so we can agree on scope. Documentation fixes and small bug fixes can go straight to a pull request. Maintainers review and merge contributions; contributors do not need repository write access.

## First contributions

Look for `good first issue` and `help wanted`. Useful starting points: Windows instructions, small examples, clearer diagnostics, and parser parity tests. Comment on an issue to coordinate work and include reproduction steps in bug reports.

By contributing, you agree that your contributions may be distributed under this repository's MIT license. Please follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
