"""LlmRequestConventions: provider-agnostic chat/completions argument shaping."""

from __future__ import annotations

from typing import Any, Dict


REASONING_FAMILIES = ("o1", "o3", "o4", "gpt-5", "deepseek-reasoner", "reasoner")
FIXED_TEMPERATURE = ("moonshot", "kimi")


def apply_llm_request_conventions(kwargs: Dict[str, Any], model: str) -> Dict[str, Any]:
    out = dict(kwargs)
    model_l = (model or "").lower()
    uses_completion_tokens = any(tag in model_l for tag in REASONING_FAMILIES)
    if uses_completion_tokens and "max_tokens" in out:
        out["max_completion_tokens"] = out.pop("max_tokens")
        out.pop("temperature", None)
    if any(tag in model_l for tag in FIXED_TEMPERATURE):
        out.pop("temperature", None)
    if "deepseek" in model_l:
        out.pop("thinking", None)
        if isinstance(out.get("extra_body"), dict):
            out["extra_body"].pop("thinking", None)
    return out
