"""Provider configuration and dependency-free cloud/local HTTP adapters."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROVIDERS = {
    "gemini": ("GEMINI_API_KEY", "gemini-3.8-flash"),
    "openai": ("OPENAI_API_KEY", "gpt-5-mini"),
    "anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-4-6"),
    "groq": ("GROQ_API_KEY", "openai/gpt-oss-20b"),
    "ollama": (None, "llama3.2"),
}


def provider_settings(ast):
    options = ast.generate.options if ast.generate else {}
    provider = options.get("provider", "gemini")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError("Unsupported provider. Choose gemini, openai, anthropic, groq, or ollama.")
    key_name, default_model = PROVIDERS[provider]
    model = ast.generate.model if ast.generate and ast.generate.model else default_model
    max_tokens = options.get("max_tokens", 4096)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer.")
    temperature = ast.generate.temperature if ast.generate else None
    if provider == "gemini" and temperature is None:
        temperature = 0.2
    return provider, key_name, model, temperature, max_tokens


def ollama_endpoint():
    """Resolve a user-configured server URL, never a prompt-supplied endpoint."""
    from urllib.parse import urlsplit
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) server URL without credentials, query, or fragment.")
    return base + "/api/chat"


def provider_request(provider, model, system, prompt, schema, history, temperature=None, max_tokens=4096):
    """Build a request without secrets. Also embedded in generated Python modules."""
    messages = [{"role": "assistant" if turn["role"] == "model" else turn["role"], "content": turn["text"]} for turn in history]
    messages.append({"role": "user", "content": prompt})
    instructions = system + "\nReturn ONLY a JSON object matching this schema:\n" + json.dumps(schema)
    if provider == "openai":
        endpoint = "https://api.openai.com/v1/responses"
        payload = {"model": model, "instructions": instructions, "input": messages, "store": False,
                   "max_output_tokens": max_tokens,
                   "text": {"format": {"type": "json_schema", "name": "aip_output", "schema": schema, "strict": False}}}
    elif provider == "anthropic":
        endpoint = "https://api.anthropic.com/v1/messages"
        payload = {"model": model, "system": instructions, "messages": messages, "max_tokens": max_tokens}
    elif provider == "groq":
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
        payload = {"model": model, "messages": [{"role": "system", "content": instructions}] + messages,
                   "max_completion_tokens": max_tokens, "stream": False, "response_format": {"type": "json_object"}}
    elif provider == "ollama":
        endpoint = ollama_endpoint()
        payload = {"model": model, "messages": [{"role": "system", "content": instructions}] + messages,
                   "stream": False, "format": schema, "options": {"num_predict": max_tokens}}
    else:
        raise ValueError("HTTP adapter requires openai, anthropic, groq, or ollama.")
    if temperature is not None:
        if provider == "ollama":
            payload["options"]["temperature"] = temperature
        else:
            payload["temperature"] = temperature
    return endpoint, payload


def provider_response(provider, data):
    """Read text only; refusals, incomplete replies, and empty output fail clearly."""
    if provider == "openai":
        if data.get("status") in ("incomplete", "failed", "cancelled"):
            raise RuntimeError("OpenAI returned an incomplete or failed response.")
        parts = [part for item in data.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
        if any(part.get("type") == "refusal" for part in parts):
            raise RuntimeError("OpenAI refused the request.")
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "output_text")
    elif provider == "anthropic":
        if data.get("stop_reason") in ("max_tokens", "refusal"):
            raise RuntimeError("Anthropic returned a truncated response or refusal.")
        text = "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
    elif provider == "groq":
        choices = data.get("choices", [])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})
        if choice.get("finish_reason") != "stop" or message.get("refusal"):
            raise RuntimeError("Groq returned an incomplete response or refusal.")
        text = message.get("content", "")
    elif provider == "ollama":
        if data.get("error") or data.get("done") is not True or data.get("done_reason") != "stop":
            raise RuntimeError("Ollama returned an error or incomplete response.")
        text = data.get("message", {}).get("content", "")
    else:
        raise ValueError("Unsupported response provider.")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"{provider} returned no usable text.")
    return text


def request_provider(provider, api_key, model, system, prompt, schema, history, temperature=None, max_tokens=4096):
    endpoint, payload = provider_request(provider, model, system, prompt, schema, history, temperature, max_tokens)
    headers = {"Content-Type": "application/json"}
    if provider in ("openai", "groq"):
        headers["Authorization"] = "Bearer " + api_key
    elif provider == "anthropic":
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as error:
        # Never echo headers, keys, or arbitrary response bodies into caller logs.
        raise RuntimeError(f"{provider} API request failed (HTTP {error.code}).") from None
    except URLError:
        raise RuntimeError(f"{provider} API connection failed.") from None
    return provider_response(provider, data)


class ProviderClient:
    """Adapter retaining the custom/mock client interface used by the runtime."""
    def __init__(self, provider, max_tokens=4096):
        self.provider = provider
        self.max_tokens = max_tokens
        key_name = PROVIDERS[provider][0]
        self.api_key = os.environ.get(key_name) if key_name else None
        if key_name and (not self.api_key or self.api_key.startswith("MY_")):
            raise ValueError(f"{key_name} is required for {provider}. Use --mock for an offline run.")
        self.models = self

    def generate_content(self, model, contents, config):
        from types import SimpleNamespace
        text = request_provider(self.provider, self.api_key, model, config["system_instruction"], contents,
                                config["response_schema"], config.get("history", []), config["temperature"], self.max_tokens)
        return SimpleNamespace(text=text)
