"""SSE envelope helpers matching {type, payload, message}."""

import json
from typing import Any, Dict, Optional


def sse_event(event_type: str, payload: Any = None, message: str = "") -> Dict[str, Any]:
    return {
        "type": event_type,
        "payload": payload if payload is not None else {},
        "message": message,
    }


def sse_status(stage: str, message: str, step_id: Optional[int] = None, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"stage": stage, **extra}
    if step_id is not None:
        payload["step_id"] = step_id
    return sse_event("status", payload, message)


def sse_result(payload: Any, message: str = "") -> Dict[str, Any]:
    return sse_event("result", payload, message)


def sse_done(message: str = "") -> Dict[str, Any]:
    return sse_event("done", {}, message)


def sse_error(message: str, payload: Any = None) -> Dict[str, Any]:
    return sse_event("error", payload if payload is not None else {}, message)


def format_sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
