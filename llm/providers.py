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

TIMEOUT = 120
RETRY_STATUS = {429, 500, 502, 503, 504}


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _mime(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


class LLMError(RuntimeError):
    """Raised with a message the UI can show as-is."""


class GroundingUnavailable(LLMError):
    """Google Search grounding is not available (free tier, no permission, provider without it)."""


def _post(url: str, payload: dict[str, Any], headers: dict[str, str], attempts: int = 4) -> requests.Response:
    last: requests.Response | None = None
    for i in range(attempts):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            if i == attempts - 1:
                raise LLMError(f"cannot reach {url.split('?')[0]}: {exc}") from exc
            time.sleep(2**i)
            continue
        if res.status_code not in RETRY_STATUS:
            return res
        last = res
        retry_after = res.headers.get("Retry-After")
        time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** (i + 1))
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
        return _post(f"{self.base}/interactions", payload, self._headers())

    def _generate_content(self, model: str, prompt: str, schema: dict | None, system: str) -> requests.Response:
        cfg: dict[str, Any] = {"temperature": self.temperature}
        if schema:
            cfg.update({"responseMimeType": "application/json", "responseJsonSchema": schema})
        payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return _post(f"{self.base}/models/{model}:generateContent", payload, self._headers())

    def _call(self, prompt: str, schema: dict | None, system: str) -> str:
        from llm import usage

        usage.check_limit()
        errors = []
        for model in [self.model, *[m for m in self.fallbacks if m != self.model]]:
            for call in (self._interactions, self._generate_content):
                res = call(model, prompt, schema, system)
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

    def _chat(self, prompt: str, system: str, schema: dict | None) -> str:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not set. Add it in Settings.")
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        res = _post(f"{self.base_url.rstrip('/')}/chat/completions", payload, headers)
        if not res.ok:
            raise LLMError(f"OpenAI-compatible HTTP {res.status_code}: {res.text[:200]}")
        return res.json()["choices"][0]["message"]["content"]

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
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        res = _post(f"{self.base_url.rstrip('/')}/chat/completions", payload, headers)
        if not res.ok:
            raise LLMError(f"OpenAI-compatible vision HTTP {res.status_code}: {res.text[:200]}")
        return extract_json(res.json()["choices"][0]["message"]["content"])


def get_provider(name: str | None = None) -> Provider:
    cfg = settings.load()["llm"]
    name = name or cfg["provider"]
    temp = float(cfg.get("temperature", 0.8))
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
    raise LLMError(f"unknown LLM provider '{name}' (use gemini, ollama or openai)")
