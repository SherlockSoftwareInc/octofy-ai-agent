"""Provider-agnostic LLM client wrapping existing llm_service + request conventions."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

from app.models.pipeline import TokenUsage
from app.services.llm_conventions import apply_llm_request_conventions


class LlmClient:
    def __init__(self):
        self._lock = threading.Lock()
        self.token_usage = TokenUsage()

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        presence_penalty: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        from app.services.llm_service import get_llm_service

        svc = get_llm_service()
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if presence_penalty is not None:
            kwargs["presence_penalty"] = presence_penalty
        if model:
            kwargs["model"] = model
        kwargs = apply_llm_request_conventions(kwargs, model or getattr(svc, "model", "") or "")
        content = ""
        usage = TokenUsage()
        try:
            client = getattr(svc, "client", None)
            if client is None:
                content = svc.chat_completion(messages, temperature=kwargs.get("temperature", 0) or 0)
            else:
                call_kwargs = {k: v for k, v in kwargs.items() if k != "model"}
                model_name = kwargs.get("model") or svc.model
                response = client.chat.completions.create(model=model_name, **call_kwargs)
                choice = response.choices[0].message
                content = choice.content or getattr(choice, "reasoning_content", None) or ""
                if getattr(response, "usage", None):
                    usage = TokenUsage(
                        prompt_tokens=int(response.usage.prompt_tokens or 0),
                        completion_tokens=int(response.usage.completion_tokens or 0),
                        total_tokens=int(response.usage.total_tokens or 0),
                    )
        except Exception as exc:
            content = f""
            raise RuntimeError(f"LLM completion failed: {exc}") from exc
        with self._lock:
            self.token_usage.add(usage)
        return content or ""

    def complete_json(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        text = self.complete(messages, **kwargs)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            return {}
