# Invoice extraction, end to end

This example turns synthetic invoice text into a typed object, including a nested vendor and a list of line items. It is a starting point for application integration, not an accounting system or proof of extraction accuracy.

## 1. Check the contract offline

Install AIP from source using the [quick start](quickstart.md). The example files are `examples/invoice-extraction.aiprompt`, `examples/invoice-extraction-data.json`, and the hand-authored reference `examples/invoice-extraction-result.json`.

```bash
aip check examples/invoice-extraction.aiprompt
aip schema examples/invoice-extraction.aiprompt
aip run examples/invoice-extraction.aiprompt --file examples/invoice-extraction-data.json --mock --pretty
```

No API key is needed for these commands. The explicit mock run returns schema-shaped fixture values: `"Mock value"` for strings, zero for numbers, and empty lists for items. It does **not** extract the invoice. The CLI labels the mock on stderr while keeping stdout valid JSON. Missing credentials without `--mock` now produce an error.

The reference result describes the synthetic invoice: two notebooks at USD 12.50 each, total USD 25.00. It is a human-written comparison example, not a recorded model response.

## 2. Run a real extraction

The supplied contract uses Gemini. Set `GEMINI_API_KEY` in your shell, then run without `--mock`:

```bash
aip run examples/invoice-extraction.aiprompt --file examples/invoice-extraction-data.json --pretty
```

To use another provider, edit the contract's `provider`, `model`, and supported settings; see [providers](providers.md). Live calls use your provider account and may incur charges. A model result can differ from the reference or contain factual mistakes despite passing schema validation. Review financial values before using them.

## 3. Generate Python

```bash
aip compile examples/invoice-extraction.aiprompt --target python --out generated/invoice.py
```

With Pydantic, google-genai, and the Gemini key configured:

```python
import json
from generated.invoice import run_invoiceresult

with open('examples/invoice-extraction-data.json', encoding='utf-8') as file:
    data = json.load(file)
result = run_invoiceresult(invoice_text=data['invoice_text'])
print(result.vendor.name)
print(result.total)
```

This generated function makes a real request. For offline tests of the contract, use `run_aip(source, variables, mock=True)` or the CLI mock run above.

## 4. Generate PHP or use Laravel

```bash
aip compile examples/invoice-extraction.aiprompt --target php --out app/AI/InvoiceExtractionAip.php
php -l app/AI/InvoiceExtractionAip.php
```

In Laravel, add a Gemini entry in `config/services.php`, using your normal environment secret:

```php
'gemini' => ['key' => env('GEMINI_API_KEY')],
```

Call the compiled class from your application service:

```php
use App\AI\InvoiceExtractionAip;

$invoice = InvoiceExtractionAip::run(
    invoice_text: $invoiceText,
    apiKey: config('services.gemini.key'),
    maxRetries: 2,
);

echo $invoice->vendor['name'];
echo $invoice->total;
```

Laravel's normal `App` autoloading matches the generated namespace. Outside Laravel, require the generated file before calling it. PHP 8.1+, cURL, and JSON are needed; Python is used only at compilation. Provider errors or exhausted validation retries throw exceptions, which the application should handle.

## What the tests verify

Offline tests parse the shipped contract, validate the reference against its schema, reject invalid nested values, exercise explicit mock execution, and compile and execute the generated Python/PHP validation paths. They do not claim that a live model extracted the reference result.
