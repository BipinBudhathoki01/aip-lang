# PHP & Laravel integration

Compile the prompt during development or deployment. PHP 8.1+ with cURL and JSON is required at runtime; Python is only required to compile.

```bash
aip compile examples/examiner.aiprompt --target php --out app/AI/ExaminerAip.php
php -l app/AI/ExaminerAip.php
```

In Laravel, the default `App\AI` namespace matches the example path:

```php
use App\AI\ExaminerAip;

$result = ExaminerAip::run(
    name: 'Ada',
    text: 'An example submission.',
    apiKey: config('services.gemini.key'),
    maxRetries: 2,
);

echo $result->score;
```

Configure `services.gemini.key` in Laravel's `config/services.php` using your normal secret management. Laravel deployments often cache configuration; passing the key explicitly is more predictable than relying on `getenv()`.

Outside Laravel, require the generated file before using its class. The generated file contains the executor and its result DTO together. Use distinct target class names when loading several generated files into the same namespace.

Nested objects and dictionaries are represented as PHP arrays, lists as arrays, and primitives as native properties. The generated validator checks the supported nested schema before DTO construction. Errors can still occur due to network failures, provider access, or exhausted retries. Do not treat a valid result as proof that its content is correct.
