import re
from typing import Dict


PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ID_RE = re.compile(r"\b\d{6}(19|20)?\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")
CARD_RE = re.compile(r"\b\d{13,19}\b")


def mask_sensitive_data(text: str) -> str:
    masked = PHONE_RE.sub("<<phone>>", text)
    masked = EMAIL_RE.sub("<<email>>", masked)
    masked = ID_RE.sub("<<id>>", masked)
    masked = CARD_RE.sub("<<card>>", masked)
    return masked


def redact_payload(payload: Dict) -> Dict:
    safe = {}
    for k, v in payload.items():
        if isinstance(v, str):
            safe[k] = mask_sensitive_data(v)
        else:
            safe[k] = v
    return safe
