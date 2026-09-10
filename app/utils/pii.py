"""PII masking for request intake. Downstream work uses the masked query."""

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def mask_pii(text: str) -> str:
    if not text:
        return text
    masked = _EMAIL.sub("[EMAIL]", text)
    masked = _SSN.sub("[SSN]", masked)
    masked = _PHONE.sub("[PHONE]", masked)
    masked = _CARD.sub("[CARD]", masked)
    return masked
