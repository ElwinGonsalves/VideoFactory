"""One interface over Gemini (default), Ollama (offline) and any OpenAI-compatible endpoint.

    provider = get_provider()                       # from Settings / .env
    data = provider.generate_json(prompt, schema)   # validated dict

All providers: JSON-schema constrained output, retries with backoff on 429/5xx, and clear
errors that say which setting to fix. Keys come from `.env`; they are never logged.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from common import settings

TIMEOUT = (10, 120)  # connect fast-fails (dead network / blocked host); a long script may take ~2 min to write
RETRY_STATUS = {429, 500, 502, 503, 504}
GEMINI_TIMEOUT = (10, 60)  # per request: a 50 s script normally comes back in 10-30 s
GEMINI_BUDGET_S = 180  # all Gemini models and endpoints together, so a backup brain still gets its turn
NET_ATTEMPTS = 2  # unreachable host: give up quickly so the fallback chain can try another provider
MAX_429_WAIT = 6.0  # seconds; a longer Retry-After means "quota gone", better served by the next model


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _mime(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


class LLMError(RuntimeError):
    """Raised with a message the UI can show as-is."""


class GroundingUnavailable(LLMError):
    """Google Search grounding is not available (free tier, no permission, provider without it)."""


def _post(
    url: str, payload: dict[str, Any], headers: dict[str, str], attempts: int = 4, timeout: Any = None
) -> requests.Response:
    last: requests.Response | None = None
    for i in range(attempts):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=timeout or TIMEOUT)
        except requests.RequestException as exc:
            # A read timeout means the model is stuck, not a network blip: retrying doubles the wait.
            if isinstance(exc, requests.ReadTimeout) or i >= min(attempts, NET_ATTEMPTS) - 1:
                raise LLMError(f"cannot reach {url.split('?')[0]}: {exc}") from exc
            time.sleep(2**i)
            continue
        if res.status_code not in RETRY_STATUS:
            return res
        last = res
        retry_after = res.headers.get("Retry-After")
        wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 2 ** (i + 1)
        if res.status_code == 429 and (wait > MAX_429_WAIT or i >= 1):
            return res  # quota, not a blip: let the caller move to the next model / provider now
        time.sleep(min(wait, 30))
    assert last is not None
    return last


def extract_json(text: str) -> Any:
    """Parse JSON even when a model wraps it in ```json fences or adds a sentence around it."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise LLMError(f"model did not return JSON: {text[:200]}")


_SKIP_KEYS = {"input", "usage", "usage_metadata", "usageMetadata", "system_instruction", "promptFeedback"}


def _find_text(obj: Any) -> str | None:
    """First non-empty answer text anywhere in a response (API shapes drift).

    Skips echoed input, usage blocks and reasoning ("thought") parts.
    """
    if isinstance(obj, dict):
        if obj.get("thought") is True or obj.get("type") in ("thought", "thinking", "reasoning"):
            return None
        for key in ("output_text", "outputText", "text"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v
        for k, v in obj.items():
            if k in _SKIP_KEYS:
                continue
            found = _find_text(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_text(v)
            if found:
                return found
    return None


@dataclass
class Provider:
    name: str
    model: str
    temperature: float = 0.8

    def generate_text(self, prompt: str, system: str = "") -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:  # pragma: no cover
        raise NotImplementedError

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        raise LLMError(f"{self.name} vision is not supported; use Gemini or a vision model")

    def grounded_research(self, query: str, system: str = "") -> dict[str, Any]:
        """Web-grounded notes + cited sources, or GroundingUnavailable. Only Gemini implements it."""
        raise GroundingUnavailable(f"{self.name} has no web grounding")

    def ping(self) -> str:
        """Cheap connectivity test for the Settings page."""
        out = self.generate_json(
            'Reply with {"ok": true}.',
            {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        )
        return f"{self.name}:{self.model} ok={out.get('ok')}"


@dataclass
class GeminiProvider(Provider):
    api_key: str = ""
    fallbacks: list[str] = field(default_factory=list)
    base: str = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set. Add it in Settings (or .env).")
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _interactions(self, model: str, prompt: str, schema: dict | None, system: str) -> requests.Response:
        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "store": False,  # nothing kept server-side; we never reuse interaction ids
            "generation_config": {"temperature": self.temperature},
        }
        if system:
            payload["system_instruction"] = system
        if schema:
            payload["response_format"] = {"type": "text", "mime_type": "application/json", "schema": schema}
        return _post(f"{self.base}/interactions", payload, self._headers(), timeout=GEMINI_TIMEOUT)

    def _generate_content(self, model: str, prompt: str, schema: dict | None, system: str) -> requests.Response:
        cfg: dict[str, Any] = {"temperature": self.temperature}
        if schema:
            cfg.update({"responseMimeType": "application/json", "responseJsonSchema": schema})
        payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return _post(f"{self.base}/models/{model}:generateContent", payload, self._headers(), timeout=GEMINI_TIMEOUT)

    def _call(self, prompt: str, schema: dict | None, system: str) -> str:
        from llm import usage

        usage.check_limit()
        errors: list[str] = []
        deadline = time.monotonic() + GEMINI_BUDGET_S
        # generateContent first: it is the long-standing endpoint. /interactions is newer and has been seen to
        # hang until the read timeout for some models, so it is only the second try.
        for model in [self.model, *[m for m in self.fallbacks if m != self.model]]:
            for call in (self._generate_content, self._interactions):
                if time.monotonic() > deadline:
                    errors.append(f"gave up after {GEMINI_BUDGET_S}s")
                    raise LLMError("Gemini failed. " + " | ".join(errors[-4:]))
                try:
                    res = call(model, prompt, schema, system)
                except LLMError as exc:  # timeout / connection reset: try the other endpoint, then the next model
                    errors.append(f"{model} via {call.__name__.strip('_')}: {str(exc)[-120:]}")
                    print(f"  {model} via {call.__name__.strip('_')} did not answer; trying the next one", flush=True)
                    continue
                if res.ok:
                    text = _find_text(res.json())
                    if text:
                        self.model = model  # remember the one that worked for this run
                        usage.record("gemini", model, res.json())
                        return text
                    errors.append(f"{model}: empty response")
                    continue
                if res.status_code in (401, 403):
                    raise LLMError(
                        f"Gemini rejected the API key ({res.status_code}). Check GEMINI_API_KEY in Settings."
                    )
                errors.append(f"{model} via {call.__name__.strip('_')}: HTTP {res.status_code} {res.text[:160]}")
                if res.status_code == 429:
                    break  # rate limited: try the next model rather than the other endpoint
        raise LLMError("Gemini failed. " + " | ".join(errors[-4:]))

    def generate_text(self, prompt: str, system: str = "") -> str:
        return self._call(prompt, None, system)

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:
        return extract_json(self._call(prompt, schema, system))

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        parts: list[dict[str, Any]] = [{"inline_data": {"mime_type": _mime(p), "data": _b64(p)}} for p in images]
        parts.append({"text": prompt})
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        from llm import usage

        usage.check_limit()
        errors = []
        for model in [self.model, *[m for m in self.fallbacks if m != self.model]]:
            res = _post(f"{self.base}/models/{model}:generateContent", payload, self._headers())
            if res.ok and (text := _find_text(res.json())):
                usage.record("gemini", model, res.json())
                return extract_json(text)
            errors.append(f"{model}: HTTP {res.status_code} {res.text[:120]}")
        raise LLMError("Gemini vision failed. " + " | ".join(errors[-3:]))

    def grounded_research(self, query: str, system: str = "") -> dict[str, Any]:
        """generateContent with the google_search tool. Free-tier keys are refused; callers then fall back.

        Returns {"notes": text, "sources": [{"title", "url"}], "queries": [...]}.
        """
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        from llm import usage

        usage.check_limit()
        res = _post(f"{self.base}/models/{self.model}:generateContent", payload, self._headers(), attempts=2)
        if res.ok:
            usage.record("gemini", self.model, res.json())
        if not res.ok:
            raise GroundingUnavailable(f"Google Search grounding refused (HTTP {res.status_code}): {res.text[:160]}")
        body = res.json()
        cand = ((body.get("candidates") or [{}])[0]) if isinstance(body, dict) else {}
        meta = cand.get("groundingMetadata") or {}
        sources, seen = [], set()
        for chunk in meta.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            url = web.get("uri")
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": str(web.get("title") or url)[:120], "url": url})
        notes = _find_text(cand.get("content") or {})
        if not notes or not sources:
            raise GroundingUnavailable("the model answered without citing any web source")
        return {"notes": notes, "sources": sources, "queries": list(meta.get("webSearchQueries") or [])}

    def list_models(self) -> list[str]:
        res = requests.get(f"{self.base}/models", headers=self._headers(), timeout=30)
        if not res.ok:
            raise LLMError(f"list models failed: HTTP {res.status_code}")
        return sorted(m["name"].removeprefix("models/") for m in res.json().get("models", []))


@dataclass
class OllamaProvider(Provider):
    host: str = "http://127.0.0.1:11434"

    def _chat(self, prompt: str, system: str, fmt: Any) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if fmt is not None:
            payload["format"] = fmt
        res = _post(f"{self.host.rstrip('/')}/api/chat", payload, {"Content-Type": "application/json"})
        if res.status_code == 404:
            raise LLMError(f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}")
        if not res.ok:
            raise LLMError(f"Ollama HTTP {res.status_code}: {res.text[:200]}")
        return res.json()["message"]["content"]

    def generate_text(self, prompt: str, system: str = "") -> str:
        return self._chat(prompt, system, None)

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:
        return extract_json(self._chat(prompt, system, schema))

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        """Works with vision models only (e.g. `ollama pull qwen2.5vl:7b`)."""
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt, "images": [_b64(p) for p in images]}
        ]
        payload = {"model": self.model, "messages": messages, "stream": False, "format": schema}
        res = _post(f"{self.host.rstrip('/')}/api/chat", payload, {"Content-Type": "application/json"})
        if not res.ok:
            raise LLMError(f"Ollama vision HTTP {res.status_code}: {res.text[:200]}")
        return extract_json(res.json()["message"]["content"])


@dataclass
class OpenAICompatProvider(Provider):
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"

    key_name: str = "OPENAI_API_KEY"
    label: str = "OpenAI-compatible"
    # json_schema (strict structured output) | json_object (JSON mode + schema in the prompt). Groq and most
    # free OpenRouter models only do JSON mode, so they get the schema spelled out in the prompt instead.
    json_mode: str = "json_schema"
    extra_headers: dict[str, str] = field(default_factory=dict)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", **self.extra_headers}

    def _chat(self, prompt: str, system: str, schema: dict | None) -> str:
        if not self.api_key:
            raise LLMError(f"{self.key_name} is not set. Add it in Settings.")
        if schema and self.json_mode == "json_object":
            prompt = f"{prompt}\n\nReply with one JSON object only, matching this JSON Schema:\n{json.dumps(schema)}"
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if schema:
            payload["response_format"] = (
                {"type": "json_object"}
                if self.json_mode == "json_object"
                else {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
            )
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        res = _post(url, payload, self._headers())
        if res.status_code == 400 and schema and "response_format" in res.text:
            # this model has no JSON mode at all: ask in words, extract_json still finds the object
            payload.pop("response_format")
            res = _post(url, payload, self._headers())
        if res.status_code in (401, 403):
            raise LLMError(f"{self.label} rejected the API key ({res.status_code}). Check {self.key_name} in Settings.")
        if res.status_code == 429:
            raise LLMError(
                f"{self.label} rate limit reached (429) for {self.model}. Wait a minute or pick another model."
            )
        if not res.ok:
            raise LLMError(f"{self.label} HTTP {res.status_code}: {res.text[:200]}")
        content = (res.json().get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not content.strip():
            raise LLMError(f"{self.label} returned an empty answer from {self.model}")
        return content

    def list_models(self) -> list[str]:
        res = requests.get(f"{self.base_url.rstrip('/')}/models", headers=self._headers(), timeout=TIMEOUT)
        if not res.ok:
            raise LLMError(f"{self.label} HTTP {res.status_code}: {res.text[:200]}")
        ids = sorted(m["id"] for m in res.json().get("data", []) if m.get("id"))
        if self.name == "openrouter":  # the free ones are what this project is for
            ids = [i for i in ids if i.endswith(":free")]
        return ids

    def generate_text(self, prompt: str, system: str = "") -> str:
        return self._chat(prompt, system, None)

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:
        return extract_json(self._chat(prompt, system, schema))

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "image_url": {"url": f"data:{_mime(p)};base64,{_b64(p)}"}} for p in images]
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}},
        }
        if self.json_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
            content[0]["text"] += (
                f"\n\nReply with one JSON object only, matching this JSON Schema:\n{json.dumps(schema)}"
            )
        res = _post(f"{self.base_url.rstrip('/')}/chat/completions", payload, self._headers())
        if not res.ok:
            raise LLMError(f"{self.label} vision HTTP {res.status_code} ({self.model}): {res.text[:200]}")
        return extract_json(res.json()["choices"][0]["message"]["content"])


PROVIDER_NAMES = ("gemini", "groq", "openrouter", "ollama", "openai")
# Provider -> the .env key it needs (ollama needs none). Used to pick fallbacks that are actually set up.
PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass
class ChainProvider(Provider):
    """The chosen provider first; on a failure (bad key, quota, outage, empty answer) the next one that has a key.

    Grounded research stays on the first provider only: it is optional and has its own fallback.
    """

    chain: list[Provider] = field(default_factory=list)

    def _try(self, method: str, *args: Any) -> Any:
        errors: list[str] = []
        for p in self.chain:
            try:
                out = getattr(p, method)(*args)
                if errors:
                    print(f"  used {p.name}:{p.model} after: {'; '.join(errors)}", flush=True)
                return out
            except GroundingUnavailable:
                raise
            except LLMError as exc:
                errors.append(f"{p.name} failed ({str(exc)[:140]})")
        raise LLMError(" | ".join(errors) or "no language model is configured")

    def generate_text(self, prompt: str, system: str = "") -> str:
        return self._try("generate_text", prompt, system)

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:
        return self._try("generate_json", prompt, schema, system)

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        return self._try("vision_json", prompt, schema, images, system)

    def grounded_research(self, query: str, system: str = "") -> dict[str, Any]:
        return self.chain[0].grounded_research(query, system)


def get_provider(name: str | None = None, *, chain: bool = True) -> Provider:
    """The configured provider, wrapped with fallbacks from `llm.fallback_providers` that have a key."""
    cfg = settings.load()["llm"]
    first = single_provider(name or cfg["provider"])
    if not chain or name:
        return first
    rest = [
        single_provider(n)
        for n in cfg.get("fallback_providers", [])
        if n != first.name and n in PROVIDER_NAMES and (n not in PROVIDER_KEYS or settings.env(PROVIDER_KEYS[n]))
    ]
    if not rest:
        return first
    return ChainProvider(first.name, first.model, first.temperature, chain=[first, *rest])


def single_provider(name: str) -> Provider:
    cfg = settings.load()["llm"]
    temp = float(cfg.get("temperature", 0.8))
    if name == "groq":
        return OpenAICompatProvider(
            "groq",
            cfg.get("groq_model") or "llama-3.3-70b-versatile",
            temp,
            api_key=settings.env("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            key_name="GROQ_API_KEY",
            label="Groq",
            json_mode="json_object",
        )
    if name == "openrouter":
        return OpenAICompatProvider(
            "openrouter",
            cfg.get("openrouter_model") or "meta-llama/llama-3.3-70b-instruct:free",
            temp,
            api_key=settings.env("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            key_name="OPENROUTER_API_KEY",
            label="OpenRouter",
            json_mode="json_object",
            # OpenRouter's app attribution headers (optional, no personal data)
            extra_headers={
                "HTTP-Referer": "https://github.com/ElwinGonsalves/VideoFactory",
                "X-Title": "video-factory",
            },
        )
    if name == "gemini":
        return GeminiProvider(
            "gemini",
            cfg["gemini_model"],
            temp,
            api_key=settings.env("GEMINI_API_KEY"),
            fallbacks=list(cfg.get("gemini_fallback_models", [])),
        )
    if name == "ollama":
        return OllamaProvider(
            "ollama", cfg["ollama_model"], temp, host=settings.env("OLLAMA_HOST", "http://127.0.0.1:11434")
        )
    if name == "openai":
        return OpenAICompatProvider(
            "openai",
            cfg["openai_model"],
            temp,
            api_key=settings.env("OPENAI_API_KEY"),
            base_url=settings.env("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    raise LLMError(f"unknown LLM provider '{name}' (use {', '.join(PROVIDER_NAMES)})")
