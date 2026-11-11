# Quick start

## Install from source

Use Python 3.10 or newer. A PyPI release is not available from this project yet.

```bash
git clone https://github.com/BipinBudhathoki01/aip-lang.git
cd aip-lang
python -m venv .venv
```

Activate on macOS/Linux with `source .venv/bin/activate`, or in Windows PowerShell with `.\.venv\Scripts\Activate.ps1`.

```bash
python -m pip install -e .
aip check examples/examiner.aiprompt
aip run examples/examiner.aiprompt --file examples/data.json --mock --pretty
```

The mock returns a deterministic examiner fixture. It verifies integration without calling a model or assessing the submitted text.

## Live calls

Set `GEMINI_API_KEY` in your shell. In PowerShell use `$env:GEMINI_API_KEY = 'your-key'`; on macOS/Linux use `export GEMINI_API_KEY='your-key'`. Then run without `--mock`. Choose a model available to your account. Live requests may incur provider charges; tests do not require them.

The CLI currently falls back to mock mode when the key is missing and warns on stderr. A `.env` file is loaded by the local web server only, not the Python CLI.

## Local playground

Install Node.js 22.12+ and the Python dependencies above, then:

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The editor previews source locally; Parse with Python and Run mock send the current source and variables to the local server. Run mock synthesizes schema-shaped fixture values, not an AI answer. No model requests happen from the playground.

The hosted playground supports browser previews only. Start the local server to enable Python execution.
