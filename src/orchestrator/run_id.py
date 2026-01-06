from __future__ import annotations

import hashlib

RUN_ID_FIELDS = (
    "symbol",
    "engine_timestamp_ms",
    "cut_end_ingest_seq",
    "engine_mode",
)


def derive_run_id(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    cut_end_ingest_seq: int,
    engine_mode: str,
) -> str:
    payload = f"{symbol}|{engine_timestamp_ms}|{cut_end_ingest_seq}|{engine_mode}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
