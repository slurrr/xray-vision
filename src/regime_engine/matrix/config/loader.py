from __future__ import annotations

import importlib
import os
from collections.abc import Mapping, Sequence
from importlib import resources

from regime_engine.matrix.config.schema import (
    MatrixInterpreterKind,
    MatrixMode,
    MatrixRoutingConfig,
    validate_config,
)

_ROOT_KEYS = {
    "mode",
    "interpreter",
    "symbol_allowlist",
    "rollout_percent",
    "fail_closed",
    "strict_mismatch_fallback",
}


def load_matrix_routing_config() -> MatrixRoutingConfig:
    payload = _load_default_payload()
    payload = _apply_env_overrides(payload)
    config = _parse_config(payload)
    validate_config(config)
    return config


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("regime_engine.matrix.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("matrix default config must be a mapping")
    return data


def _apply_env_overrides(payload: Mapping[str, object]) -> dict[str, object]:
    overrides: dict[str, object] = dict(payload)
    if "REGIME_ENGINE_MATRIX_MODE" in os.environ:
        overrides["mode"] = os.environ["REGIME_ENGINE_MATRIX_MODE"]
    if "REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST" in os.environ:
        overrides["symbol_allowlist"] = os.environ["REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST"]
    if "REGIME_ENGINE_MATRIX_PERCENT" in os.environ:
        overrides["rollout_percent"] = os.environ["REGIME_ENGINE_MATRIX_PERCENT"]
    if "REGIME_ENGINE_MATRIX_INTERPRETER" in os.environ:
        overrides["interpreter"] = os.environ["REGIME_ENGINE_MATRIX_INTERPRETER"]
    if "REGIME_ENGINE_MATRIX_FAIL_CLOSED" in os.environ:
        overrides["fail_closed"] = os.environ["REGIME_ENGINE_MATRIX_FAIL_CLOSED"]
    if "REGIME_ENGINE_MATRIX_STRICT_MISMATCH_FALLBACK" in os.environ:
        overrides["strict_mismatch_fallback"] = os.environ[
            "REGIME_ENGINE_MATRIX_STRICT_MISMATCH_FALLBACK"
        ]
    return overrides


def _parse_config(payload: Mapping[str, object]) -> MatrixRoutingConfig:
    _reject_unknown(payload, _ROOT_KEYS, "matrix config")
    mode = _parse_mode(payload.get("mode"))
    interpreter = _parse_interpreter(payload.get("interpreter"))
    symbol_allowlist = _parse_allowlist(payload.get("symbol_allowlist"))
    rollout_percent = _parse_percent(payload.get("rollout_percent"))
    fail_closed = _parse_bool(payload.get("fail_closed"), default=True)
    strict_mismatch_fallback = _parse_bool(payload.get("strict_mismatch_fallback"), default=False)
    return MatrixRoutingConfig(
        mode=mode,
        interpreter=interpreter,
        symbol_allowlist=symbol_allowlist,
        rollout_percent=rollout_percent,
        fail_closed=fail_closed,
        strict_mismatch_fallback=strict_mismatch_fallback,
    )


def _parse_mode(value: object) -> MatrixMode:
    if isinstance(value, MatrixMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for mode in MatrixMode:
            if mode.value == normalized:
                return mode
    return MatrixMode.LEGACY_ONLY


def _parse_allowlist(value: object) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        if not value.strip():
            return frozenset()
        symbols = {item.strip() for item in value.split(",") if item.strip()}
        return frozenset(symbols)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        symbols: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("symbol_allowlist entries must be non-empty strings")
            symbols.add(item.strip())
        return frozenset(symbols)
    raise ValueError("symbol_allowlist must be a list of strings or a comma-separated string")


def _parse_interpreter(value: object) -> MatrixInterpreterKind:
    if isinstance(value, MatrixInterpreterKind):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for kind in MatrixInterpreterKind:
            if kind.value == normalized:
                return kind
    return MatrixInterpreterKind.SHADOW


def _parse_percent(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return 0
        return max(0, min(100, parsed))
    raise ValueError("rollout_percent must be an int")


def _parse_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
