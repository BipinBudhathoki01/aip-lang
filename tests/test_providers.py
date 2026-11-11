"""Provider requests and generated executors tested without external API calls."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from aip_parser import parse_aip
from aip_runtime import run_aip
from aip_lang import providers
from aip_lang.codegen_python import generate_python_code
from aip_lang.codegen_php import generate_php_code


def source(provider):
    return f'''system:
    Extract a name.
user:
    Hello {{ direct }} {{{{ $name }}}}.
generate as Result {{
    provider: "{provider}",
    max_tokens: 512,
    schema: {{ name: string }}
}}
'''


def response(provider, text):
    if provider == 'openai':
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}
    if provider == 'groq':
        return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}]}
    if provider == 'ollama':
        return {'done': True, 'done_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}
    return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': text}]}


class TestProviders(unittest.TestCase):
    def test_runtime_authentication_history_and_correction(self):
        for provider in ('openai', 'anthropic', 'groq', 'ollama'):
            with self.subTest(provider=provider):
                calls = []
                replies = iter([response(provider, '{"wrong":true}'), response(provider, '{"name":"Ada"}')])
                def transport(request, timeout):
                    self.assertEqual(timeout, 30)
                    calls.append(request)
                    return io.BytesIO(json.dumps(next(replies)).encode())
                key_name = providers.PROVIDERS[provider][0]
                env = {key_name: 'test-key'} if key_name else {}
                with patch.dict(os.environ, env, clear=True), patch.object(providers, 'urlopen', side_effect=transport):
                    result = run_aip(source(provider), {'name': 'Ada'}, max_retries=1)
                self.assertEqual(result, {'name': 'Ada'})
                self.assertEqual(len(calls), 2)
                payload = json.loads(calls[1].data)
                messages = payload['input' if provider == 'openai' else 'messages']
                if provider in ('groq', 'ollama'):
                    self.assertEqual(messages[0]['role'], 'system')
                    messages = messages[1:]
                self.assertEqual([m['role'] for m in messages], ['user', 'assistant', 'user'])
                self.assertIn('Ada', messages[0]['content'])
                self.assertIn('CORRECTION', messages[-1]['content'])
                self.assertNotIn('temperature', payload)
                headers = {key.lower(): value for key, value in calls[0].header_items()}
                if provider == 'openai':
                    self.assertEqual(calls[0].full_url, 'https://api.openai.com/v1/responses')
                    self.assertEqual(headers['authorization'], 'Bearer test-key')
                    self.assertFalse(payload['store'])
                    self.assertEqual(payload['max_output_tokens'], 512)
                    self.assertEqual(payload['text']['format']['schema']['properties']['name']['type'], 'string')
                elif provider == 'anthropic':
                    self.assertEqual(calls[0].full_url, 'https://api.anthropic.com/v1/messages')
                    self.assertEqual(headers['x-api-key'], 'test-key')
                    self.assertEqual(headers['anthropic-version'], '2023-06-01')
                    self.assertEqual(payload['max_tokens'], 512)
                elif provider == 'groq':
                    self.assertEqual(calls[0].full_url, 'https://api.groq.com/openai/v1/chat/completions')
                    self.assertEqual(headers['authorization'], 'Bearer test-key')
                    self.assertFalse(payload['stream'])
                    self.assertEqual(payload['max_completion_tokens'], 512)
                    self.assertEqual(payload['response_format'], {'type': 'json_object'})
                else:
                    self.assertEqual(calls[0].full_url, 'http://127.0.0.1:11434/api/chat')
                    self.assertNotIn('authorization', headers)
                    self.assertNotIn('x-api-key', headers)
                    self.assertNotIn('x-goog-api-key', headers)
                    self.assertFalse(payload['stream'])
                    self.assertEqual(payload['options']['num_predict'], 512)
                    self.assertEqual(payload['format']['properties']['name']['type'], 'string')

    def test_missing_credentials_and_unknown_provider_fail_before_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(providers, 'urlopen') as network:
            for provider in ('openai', 'anthropic', 'groq'):
                with self.subTest(provider=provider), self.assertRaisesRegex(ValueError, providers.PROVIDERS[provider][0]):
                    run_aip(source(provider), {'name': 'Ada'})
            with self.assertRaisesRegex(ValueError, 'Unsupported provider'):
                run_aip(source('unsupported'), {'name': 'Ada'})
            network.assert_not_called()

    def test_refusals_truncation_and_empty_output_are_errors(self):
        cases = [
            ('openai', {'status': 'incomplete'}),
            ('openai', {'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}),
            ('anthropic', {'stop_reason': 'max_tokens'}),
            ('anthropic', {'stop_reason': 'refusal'}),
            ('openai', {}), ('anthropic', {}),
            ('groq', {}), ('groq', {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}),
            ('groq', {'choices': [{'finish_reason': 'stop', 'message': {'refusal': 'No', 'content': '{}'}}]}),
            ('ollama', {}), ('ollama', {'done': False}),
            ('ollama', {'done': True, 'done_reason': 'length', 'message': {'content': '{}'}}),
            ('ollama', {'error': 'model not found'}),
        ]
        for provider, payload in cases:
            with self.subTest(provider=provider, payload=payload), self.assertRaises(RuntimeError):
                providers.provider_response(provider, payload)

    def test_http_errors_do_not_echo_keys_or_provider_body(self):
        error = HTTPError('https://api.openai.com/v1/responses', 401, 'test-key', {}, None)
        with patch.object(providers, 'urlopen', side_effect=error), self.assertRaisesRegex(RuntimeError, 'HTTP 401') as caught:
            providers.request_provider('openai', 'test-key', 'model', '', 'prompt', {}, [])
        self.assertNotIn('test-key', str(caught.exception))

    def test_generated_python_executes_each_provider_without_aip_runtime(self):
        for provider in ('openai', 'anthropic', 'groq', 'ollama'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'compiled_provider.py'
                path.write_text(generate_python_code(parse_aip(source(provider))), encoding='utf-8')
                spec = importlib.util.spec_from_file_location('compiled_provider', path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                calls = []
                replies = iter([response(provider, '{"name":2}'), response(provider, '{"name":"Ada"}')])
                def transport(request, timeout):
                    calls.append(json.loads(request.data))
                    return io.BytesIO(json.dumps(next(replies)).encode())
                try:
                    spec.loader.exec_module(module)
                    with patch.dict(os.environ, {}, clear=True), patch.object(module, 'urlopen', side_effect=transport):
                        result = module.run_result(name='Ada', api_key=None if provider == 'ollama' else 'test-key', max_retries=1)
                    self.assertEqual(result.model_dump(), {'name': 'Ada'})
                    self.assertEqual(len(calls), 2)
                    messages = calls[1]['input' if provider == 'openai' else 'messages']
                    if provider in ('groq', 'ollama'):
                        messages = messages[1:]
                    self.assertEqual(messages[1]['role'], 'assistant')
                    self.assertIn('Ada', messages[0]['content'])
                finally:
                    sys.modules.pop(spec.name, None)

    @unittest.skipUnless(shutil.which('php'), 'PHP not installed')
    def test_generated_php_provider_transport_and_retry(self):
        stub = r'''<?php
namespace App\AI;
foreach (['CURLOPT_POST','CURLOPT_RETURNTRANSFER','CURLOPT_HTTPHEADER','CURLOPT_POSTFIELDS','CURLOPT_TIMEOUT','CURLINFO_HTTP_CODE'] as $index => $name) {
    if (!defined($name)) define($name, $index + 1);
}
function curl_init($endpoint) { $GLOBALS['endpoint'] = $endpoint; return new \stdClass(); }
function curl_setopt_array($ch, $options) { $GLOBALS['calls'][] = ['url' => $GLOBALS['endpoint'], 'headers' => $options[CURLOPT_HTTPHEADER], 'body' => json_decode($options[CURLOPT_POSTFIELDS], true)]; }
function curl_exec($ch) { return json_encode(array_shift($GLOBALS['replies'])); }
function curl_getinfo($ch, $option) { return 200; }
function curl_error($ch) { return ''; }
function curl_close($ch) {}
$GLOBALS['replies'] = json_decode(stream_get_contents(STDIN), true);
$GLOBALS['calls'] = [];
require $argv[1];
$result = AipExecutor::run(name: 'Ada', apiKey: 'test-key', maxRetries: 1);
echo json_encode(['result' => $result, 'calls' => $GLOBALS['calls']]);
'''
        for provider in ('openai', 'anthropic', 'groq', 'ollama'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'Executor.php'
                path.write_text(generate_php_code(parse_aip(source(provider))), encoding='utf-8')
                runner = Path(directory) / 'run.php'
                runner.write_text(stub.replace("apiKey: 'test-key'", 'apiKey: null') if provider == 'ollama' else stub, encoding='utf-8')
                replies = [response(provider, '{"name":2}'), response(provider, '{"name":"Ada"}')]
                result = subprocess.run(['php', str(runner), str(path)], input=json.dumps(replies), capture_output=True, text=True, env={key: value for key, value in os.environ.items() if key != 'OLLAMA_BASE_URL'})
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['result'], {'name': 'Ada'})
                self.assertEqual(len(data['calls']), 2)
                messages = data['calls'][1]['body']['input' if provider == 'openai' else 'messages']
                if provider in ('groq', 'ollama'):
                    messages = messages[1:]
                self.assertEqual(messages[1]['role'], 'assistant')
                self.assertIn('Ada', messages[0]['content'])
                host = {'openai': 'openai.com', 'anthropic': 'anthropic.com', 'groq': 'groq.com', 'ollama': '127.0.0.1:11434'}[provider]
                self.assertIn(host, data['calls'][0]['url'])
                if provider == 'ollama':
                    self.assertEqual(data['calls'][0]['headers'], ['Content-Type: application/json'])
                    self.assertFalse(data['calls'][0]['body']['stream'])
                else:
                    self.assertIn('Authorization: Bearer test-key' if provider in ('openai', 'groq') else 'x-api-key: test-key', data['calls'][0]['headers'])
                if provider in ('groq', 'ollama'):
                    incomplete = {'choices': [{'finish_reason': 'length', 'message': {'content': '{"name":"Ada"}'}}]} if provider == 'groq' else {'done': True, 'done_reason': 'length', 'message': {'content': '{"name":"Ada"}'}}
                    failed = subprocess.run(['php', str(runner), str(path)], input=json.dumps([incomplete]), capture_output=True, text=True, env={key: value for key, value in os.environ.items() if key != 'OLLAMA_BASE_URL'})
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertIn('incomplete', failed.stderr)
                if provider == 'ollama':
                    env = {**os.environ, 'OLLAMA_BASE_URL': 'http://localhost:12345/prefix/'}
                    custom = subprocess.run(['php', str(runner), str(path)], input=json.dumps(replies), capture_output=True, text=True, env=env)
                    self.assertEqual(custom.returncode, 0, custom.stderr)
                    self.assertEqual(json.loads(custom.stdout)['calls'][0]['url'], 'http://localhost:12345/prefix/api/chat')
                    env['OLLAMA_BASE_URL'] = 'http://user:secret@localhost:11434'
                    invalid = subprocess.run(['php', str(runner), str(path)], input=json.dumps(replies), capture_output=True, text=True, env=env)
                    self.assertNotEqual(invalid.returncode, 0)
                    self.assertIn('OLLAMA_BASE_URL', invalid.stderr)

    def test_cli_missing_key_fails_without_mock_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prompt.aiprompt'
            path.write_text(source('openai'), encoding='utf-8')
            env = {key: value for key, value in os.environ.items() if key != 'OPENAI_API_KEY'}
            result = subprocess.run([sys.executable, 'aip_runner.py', 'run', str(path), '--data', '{"name":"Ada"}'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('OPENAI_API_KEY', result.stderr)
            self.assertEqual(result.stdout, '')

    @unittest.skipUnless(shutil.which('php'), 'PHP not installed')
    def test_cli_compiles_hyphenated_provider_example_filenames(self):
        for example in ('openai-summary', 'claude-summary', 'groq-summary', 'ollama-summary'):
            with self.subTest(example=example), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'Executor.php'
                result = subprocess.run([sys.executable, 'aip_runner.py', 'compile', f'examples/{example}.aiprompt', '--target', 'php', '--out', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                lint = subprocess.run(['php', '-l', str(path)], capture_output=True, text=True)
                self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_settings_and_retry_limits_are_checked(self):
        for invalid in ('0', '-1', 'true', '1.5'):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'max_tokens'):
                providers.provider_settings(parse_aip(source('openai').replace('max_tokens: 512', f'max_tokens: {invalid}')))
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            run_aip(source('openai'), {'name': 'Ada'}, max_retries=-1)

    def test_ollama_url_override_and_generation_options(self):
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://localhost:12345/prefix/'}):
            endpoint, payload = providers.provider_request('ollama', 'local-model', 'System', 'Hello', {}, [], 0.3, 128)
        self.assertEqual(endpoint, 'http://localhost:12345/prefix/api/chat')
        self.assertEqual(payload['options'], {'num_predict': 128, 'temperature': 0.3})
        self.assertNotIn('temperature', payload)
        for invalid in ('', 'file:///tmp/model', 'http://user:secret@localhost:11434', 'http://localhost:11434?key=x', 'http://localhost:11434#fragment'):
            with self.subTest(invalid=invalid), patch.dict(os.environ, {'OLLAMA_BASE_URL': invalid}), self.assertRaisesRegex(ValueError, 'OLLAMA_BASE_URL'):
                providers.ollama_endpoint()

    def test_cli_ollama_uses_local_server_without_api_credentials(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                text = '{"name":2}' if len(calls) == 1 else '{"name":"Ada"}'
                body = json.dumps(response('ollama', text)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'prompt.aiprompt'
                path.write_text(source('ollama'), encoding='utf-8')
                env = {key: value for key, value in os.environ.items() if not key.endswith('_API_KEY')}
                env['OLLAMA_BASE_URL'] = f'http://127.0.0.1:{server.server_port}'
                result = subprocess.run([sys.executable, 'aip_runner.py', 'run', str(path), '--data', '{"name":"Ada"}', '--retries', '1'], env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'name': 'Ada'})
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[0][0], '/api/chat')
                self.assertNotIn('Authorization', calls[0][1])
                self.assertEqual(calls[1][2]['messages'][2]['role'], 'assistant')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
