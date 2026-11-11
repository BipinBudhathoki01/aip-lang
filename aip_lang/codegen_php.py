"""
PHP Code Generator for AIP scripts.
Compiles an .aip AST into a native PHP 8.1+ class with direct REST API invocation,
zero Python subprocess overhead, and built-in auto-healing schema validation.
"""

from __future__ import annotations
import json
from aip_parser import AIPScriptAST, TypeSpec, VariableToken, TextToken
from aip_lang.providers import provider_settings


def _type_spec_to_php_type(spec: TypeSpec) -> str:
    if spec.fields is not None:
        return "array"
    primitive_map = {
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "str": "string",
        "string": "string",
        "bool": "bool",
        "boolean": "bool",
    }
    lower = spec.name.lower()
    if lower in ("list", "array"):
        return "array"
    if lower in ("dict", "map"):
        return "array"
    return primitive_map.get(lower, "string")


def generate_php_code(ast: AIPScriptAST, class_name: str = "AipExecutor", namespace: str = "App\\AI") -> str:
    """Compiles an AIPScriptAST into an independent PHP 8.1+ class."""
    target_class = ast.generate.target_class if ast.generate and ast.generate.target_class else "AnalysisResult"
    provider, key_name, model_name, temperature, max_tokens = provider_settings(ast)
    temperature_literal = 'null' if temperature is None else str(temperature)
    key_expression = f"$apiKey ?? getenv('{key_name}')" if key_name else '$apiKey'


    schema_fields = ast.generate.schema if ast.generate else {}
    variables = ast.all_variables()

    # Reconstruct prompt templates for PHP
    def tokens_to_php_template(tokens) -> str:
        parts = []
        for t in tokens:
            if isinstance(t, VariableToken):
                parts.append(f"${t.name}")
            elif isinstance(t, TextToken):
                txt = t.text.replace('\\', '\\\\').replace("'", "\\'")
                parts.append("'" + txt + "'")
            else:
                parts.append(str(t))
        return " . ".join(parts) or "''"

    system_template = tokens_to_php_template(ast.system_prompt.tokens) if ast.system_prompt else "''"
    user_template = tokens_to_php_template(ast.user_prompt.tokens) if ast.user_prompt else "''"

    # PHP properties for result DTO class
    dto_properties = []
    dto_constructor_args = []
    dto_from_array_assignments = []

    for f_name, f_spec in schema_fields.items():
        php_type = _type_spec_to_php_type(f_spec)
        dto_properties.append(f"    public {php_type} ${f_name};")
        dto_constructor_args.append(f"        {php_type} ${f_name},")
        dto_from_array_assignments.append(f"            {f_name}: $data['{f_name}'] ?? null,")

    properties_code = "\n".join(dto_properties)
    constructor_args_code = "\n".join(dto_constructor_args)
    from_array_code = "\n".join(dto_from_array_assignments)

    # Method parameters
    method_params = ", ".join([f"string ${v}" for v in variables])
    if method_params:
        method_params += ", "
    method_params += "?string $apiKey = null, int $maxRetries = 2"

    json_schema = json.dumps(ast.generate.to_json_schema()) if ast.generate else "{}"
    schema_literal = "'" + json_schema.replace("\\", "\\\\").replace("'", "\\'") + "'"

    code = f'''<?php
/**
 * Generated automatically by AIP Compiler (aip-lang).
 * DO NOT EDIT MANUALLY. Re-run `aip compile --target php` to regenerate.
 */

declare(strict_types=1);

namespace {namespace};

use RuntimeException;
use InvalidArgumentException;

class {target_class}
{{
{properties_code}

    public function __construct(
{constructor_args_code}
    ) {{
'''

    for f_name in schema_fields.keys():
        code += f"        $this->{f_name} = ${f_name};\n"

    code += f'''    }}

    public static function fromArray(array $data): self
    {{
        return new self(
{from_array_code}
        );
    }}
}}

class {class_name}
{{
    public const MODEL = {json.dumps(model_name)};
    public const PROVIDER = {json.dumps(provider)};
    public const TEMPERATURE = {temperature_literal};

    /**
     * Executes the compiled AIP prompt against the selected provider with validation retries.
     */
    public static function run({method_params}): {target_class}
    {{
        if ($maxRetries < 0) throw new InvalidArgumentException("maxRetries must be nonnegative.");
        $key = {key_expression};
        if (self::PROVIDER !== 'ollama' && !$key) {{
            throw new InvalidArgumentException("{key_name} environment variable or apiKey parameter is required.");
        }}

        $systemInstruction = trim({system_template});
        $userPrompt = trim({user_template});

        $expectedSchema = json_decode({schema_literal}, true, 512, JSON_THROW_ON_ERROR);

        $history = [];
        $currentPrompt = $userPrompt;

        for ($attempt = 0; $attempt <= $maxRetries; $attempt++) {{
            // Build Gemini REST payload
            $contents = [];
            foreach ($history as $turn) {{
                $contents[] = [
                    'role' => $turn['role'],
                    'parts' => [['text' => $turn['text']]],
                ];
            }}
            $contents[] = [
                'role' => 'user',
                'parts' => [['text' => $currentPrompt]],
            ];

            $payload = [
                'contents' => $contents,
                'generationConfig' => [
                    'responseMimeType' => 'application/json',
                    'responseSchema' => $expectedSchema,
                    'temperature' => self::TEMPERATURE,
                    'maxOutputTokens' => {max_tokens},
                ],
            ];

            if (!empty($systemInstruction)) {{
                $payload['systemInstruction'] = [
                    'parts' => [['text' => $systemInstruction]],
                ];
            }}

            $endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" . rawurlencode(self::MODEL) . ":generateContent";
            $headers = ['Content-Type: application/json', 'x-goog-api-key: ' . $key];
            if (self::PROVIDER !== 'gemini') {{
                $messages = [];
                foreach ($history as $turn) {{
                    $messages[] = ['role' => $turn['role'] === 'model' ? 'assistant' : $turn['role'], 'content' => $turn['text']];
                }}
                $messages[] = ['role' => 'user', 'content' => $currentPrompt];
                $instructions = $systemInstruction . "\\nReturn ONLY a JSON object matching this schema:\\n" . json_encode($expectedSchema);
                if (self::PROVIDER === 'openai') {{
                    $endpoint = 'https://api.openai.com/v1/responses';
                    $headers = ['Content-Type: application/json', 'Authorization: Bearer ' . $key];
                    $payload = [
                        'model' => self::MODEL, 'instructions' => $instructions, 'input' => $messages,
                        'store' => false, 'max_output_tokens' => {max_tokens},
                        'text' => ['format' => ['type' => 'json_schema', 'name' => 'aip_output', 'schema' => $expectedSchema, 'strict' => false]],
                    ];
                }} elseif (self::PROVIDER === 'anthropic') {{
                    $endpoint = 'https://api.anthropic.com/v1/messages';
                    $headers = ['Content-Type: application/json', 'x-api-key: ' . $key, 'anthropic-version: 2023-06-01'];
                    $payload = ['model' => self::MODEL, 'system' => $instructions, 'messages' => $messages, 'max_tokens' => {max_tokens}];
                }} elseif (self::PROVIDER === 'groq') {{
                    $endpoint = 'https://api.groq.com/openai/v1/chat/completions';
                    $headers = ['Content-Type: application/json', 'Authorization: Bearer ' . $key];
                    array_unshift($messages, ['role' => 'system', 'content' => $instructions]);
                    $payload = ['model' => self::MODEL, 'messages' => $messages, 'stream' => false,
                                'max_completion_tokens' => {max_tokens}, 'response_format' => ['type' => 'json_object']];
                }} else {{
                    $base = rtrim(getenv('OLLAMA_BASE_URL') !== false ? getenv('OLLAMA_BASE_URL') : 'http://127.0.0.1:11434', '/');
                    $url = parse_url($base);
                    if ($url === false || !in_array($url['scheme'] ?? '', ['http', 'https'], true) || empty($url['host']) || isset($url['user']) || isset($url['pass']) || isset($url['query']) || isset($url['fragment'])) {{
                        throw new InvalidArgumentException('OLLAMA_BASE_URL must be an HTTP(S) server URL without credentials, query, or fragment.');
                    }}
                    $endpoint = $base . '/api/chat';
                    $headers = ['Content-Type: application/json'];
                    array_unshift($messages, ['role' => 'system', 'content' => $instructions]);
                    $payload = ['model' => self::MODEL, 'messages' => $messages, 'stream' => false,
                                'format' => $expectedSchema, 'options' => ['num_predict' => {max_tokens}]];
                }}
                if (self::TEMPERATURE !== null) {{
                    if (self::PROVIDER === 'ollama') $payload['options']['temperature'] = self::TEMPERATURE;
                    else $payload['temperature'] = self::TEMPERATURE;
                }}
            }}

            $ch = curl_init($endpoint);
            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_HTTPHEADER => $headers,
                CURLOPT_POSTFIELDS => json_encode($payload),
                CURLOPT_TIMEOUT => 30,
            ]);

            $responseBody = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $curlError = curl_error($ch);
            curl_close($ch);

            if ($responseBody === false || $httpCode >= 400) {{
                throw new RuntimeException(self::PROVIDER . " API call failed (HTTP $httpCode).");
            }}

            $apiData = json_decode($responseBody, true);
            $candidateText = $apiData['candidates'][0]['content']['parts'][0]['text'] ?? null;
            if (self::PROVIDER === 'openai') {{
                if (in_array($apiData['status'] ?? '', ['incomplete', 'failed', 'cancelled'], true)) throw new RuntimeException('OpenAI returned an incomplete or failed response.');
                $candidateText = '';
                foreach ($apiData['output'] ?? [] as $item) {{
                    if (($item['type'] ?? '') !== 'message') continue;
                    foreach ($item['content'] ?? [] as $part) {{
                        if (($part['type'] ?? '') === 'refusal') throw new RuntimeException('OpenAI refused the request.');
                        if (($part['type'] ?? '') === 'output_text') $candidateText .= $part['text'] ?? '';
                    }}
                }}
            }} elseif (self::PROVIDER === 'anthropic') {{
                if (in_array($apiData['stop_reason'] ?? '', ['max_tokens', 'refusal'], true)) throw new RuntimeException('Anthropic returned a truncated response or refusal.');
                $candidateText = '';
                foreach ($apiData['content'] ?? [] as $part) {{
                    if (($part['type'] ?? '') === 'text') $candidateText .= $part['text'] ?? '';
                }}
            }} elseif (self::PROVIDER === 'groq') {{
                $choice = $apiData['choices'][0] ?? [];
                if (($choice['finish_reason'] ?? '') !== 'stop' || !empty($choice['message']['refusal'])) throw new RuntimeException('Groq returned an incomplete response or refusal.');
                $candidateText = $choice['message']['content'] ?? '';
            }} elseif (self::PROVIDER === 'ollama') {{
                if (!empty($apiData['error']) || ($apiData['done'] ?? false) !== true || ($apiData['done_reason'] ?? '') !== 'stop') throw new RuntimeException('Ollama returned an error or incomplete response.');
                $candidateText = $apiData['message']['content'] ?? '';
            }}

            if (!is_string($candidateText) || trim($candidateText) === '') {{
                throw new RuntimeException(self::PROVIDER . " returned no usable text.");
            }}

            // Validate JSON and Schema
            try {{
                return self::validateOutput($candidateText);
            }} catch (\\JsonException | InvalidArgumentException $error) {{
                $validationError = $error->getMessage();
            }}

            // Auto-Healing: Feed error back for next attempt
            if ($attempt < $maxRetries) {{
                $history[] = ['role' => 'user', 'text' => $currentPrompt];
                $history[] = ['role' => 'model', 'text' => $candidateText];
                $currentPrompt = "CORRECTION REQUIRED: Your response failed schema validation.\\nError: " . $validationError . "\\nPlease fix and return strictly conforming JSON.";
            }} else {{
                throw new RuntimeException("AIP execution failed after " . ($maxRetries + 1) . " attempts. Last error: " . $validationError);
            }}
        }}

        throw new RuntimeException("Unexpected end of retry loop.");
    }}

    public static function validateOutput(string $json): {target_class}
    {{
        $schema = json_decode({schema_literal}, true, 512, JSON_THROW_ON_ERROR);
        $value = json_decode($json, false, 512, JSON_THROW_ON_ERROR);
        self::validateValue($value, $schema, '$');
        return {target_class}::fromArray(json_decode($json, true, 512, JSON_THROW_ON_ERROR));
    }}

    private static function validateValue(mixed $value, array $schema, string $path): void
    {{
        $type = $schema['type'] ?? null;
        $valid = match ($type) {{
            'object' => is_object($value),
            'array' => is_array($value) && array_is_list($value),
            'integer' => is_int($value),
            'number' => is_int($value) || is_float($value),
            'boolean' => is_bool($value),
            'string' => is_string($value),
            default => true,
        }};
        if (!$valid) throw new InvalidArgumentException("$path: expected $type");
        if ($type === 'object') {{
            foreach ($schema['required'] ?? [] as $key) {{
                if (!property_exists($value, $key)) throw new InvalidArgumentException("$path.$key: missing field");
            }}
            foreach (get_object_vars($value) as $key => $item) {{
                $child = $schema['properties'][$key] ?? $schema['additionalProperties'] ?? null;
                if (!is_array($child)) throw new InvalidArgumentException("$path.$key: unexpected field");
                self::validateValue($item, $child, "$path.$key");
            }}
        }} elseif ($type === 'array') {{
            foreach ($value as $index => $item) self::validateValue($item, $schema['items'] ?? [], "$path.$index");
        }}
    }}
}}
'''
    return code
