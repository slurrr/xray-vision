from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from regime_engine.contracts.snapshots import (
    MISSING,
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
    is_missing,
)

_MISSING_MARKER_KEY = "__xray_missing__"
_MISSING_MARKER_OBJ: dict[str, bool] = {_MISSING_MARKER_KEY: True}


def _encode(obj: object) -> object:
    if is_missing(obj):
        return dict(_MISSING_MARKER_OBJ)

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj):
        out: dict[str, object] = {}
        for f in fields(obj):
            out[f.name] = _encode(getattr(obj, f.name))
        return out

    if isinstance(obj, dict):
        encoded: dict[str, object] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"JSON serialization requires string dict keys; got {type(k).__name__}"
                )
            encoded[k] = _encode(v)
        return encoded

    if isinstance(obj, (list, tuple)):
        return [_encode(v) for v in obj]

    return obj


def _decode(obj: object) -> object:
    if isinstance(obj, dict) and obj.keys() == {_MISSING_MARKER_KEY}:
        return MISSING

    if isinstance(obj, dict):
        return {k: _decode(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_decode(v) for v in obj]

    return obj


def snapshot_to_json_obj(snapshot: RegimeInputSnapshot) -> dict[str, object]:
    encoded = _encode(snapshot)
    if not isinstance(encoded, dict):
        raise TypeError("expected dict at top level")
    return encoded


def snapshot_from_json_obj(obj: Mapping[str, Any]) -> RegimeInputSnapshot:
    decoded = _decode(dict(obj))
    if not isinstance(decoded, dict):
        raise TypeError("expected dict at top level")

    market = decoded["market"]
    derivatives = decoded["derivatives"]
    flow = decoded["flow"]
    context = decoded["context"]
    if not all(isinstance(x, dict) for x in (market, derivatives, flow, context)):
        raise TypeError("expected nested dicts for sub-snapshots")

    return RegimeInputSnapshot(
        symbol=decoded["symbol"],
        timestamp=decoded["timestamp"],
        market=MarketSnapshot(**market),
        derivatives=DerivativesSnapshot(**derivatives),
        flow=FlowSnapshot(**flow),
        context=ContextSnapshot(**context),
    )


def dumps_snapshot_jsonl(snapshot: RegimeInputSnapshot) -> str:
    obj = snapshot_to_json_obj(snapshot)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads_snapshot_jsonl(line: str) -> RegimeInputSnapshot:
    obj = json.loads(line)
    if not isinstance(obj, dict):
        raise TypeError("expected a JSON object per line")
    return snapshot_from_json_obj(obj)
