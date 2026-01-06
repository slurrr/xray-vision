from __future__ import annotations

import base64
import json
from dataclasses import asdict
from typing import Any

from market_data.contracts import RawMarketEvent


def serialize_event(event: RawMarketEvent) -> str:
    payload, encoding = _encode_raw_payload(event.raw_payload)
    data = asdict(event)
    data["raw_payload"] = payload
    data["raw_payload_encoding"] = encoding
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _encode_raw_payload(raw_payload: bytes | str) -> tuple[str, str]:
    if isinstance(raw_payload, bytes):
        encoded = base64.b64encode(raw_payload).decode("ascii")
        return encoded, "base64"
    return raw_payload, "text"


def deserialize_event(serialized: str) -> dict[str, Any]:
    return json.loads(serialized)
