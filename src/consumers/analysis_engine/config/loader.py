from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from importlib import resources

from consumers.analysis_engine.config.schema import (
    AnalysisEngineConfig,
    ModuleConfig,
    SymbolConfig,
)

_ROOT_KEYS = {"enabled", "thresholds", "enabled_modules", "module_configs", "symbols"}
_MODULE_CONFIG_KEYS = {"module_id", "config"}
_SYMBOL_CONFIG_KEYS = {"symbol", "enabled_modules"}


def load_default_config() -> AnalysisEngineConfig:
    payload = _load_default_payload()
    return _parse_config(payload)


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("consumers.analysis_engine.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("analysis_engine default config must be a mapping")
    return data


def _parse_config(payload: Mapping[str, object]) -> AnalysisEngineConfig:
    _reject_unknown(payload, _ROOT_KEYS, "analysis_engine config")
    enabled = payload.get("enabled")
    thresholds = payload.get("thresholds")
    enabled_modules = payload.get("enabled_modules")
    module_configs = payload.get("module_configs")
    symbols = payload.get("symbols")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    if not isinstance(thresholds, Mapping):
        raise ValueError("thresholds must be a mapping")
    if not isinstance(enabled_modules, Sequence) or isinstance(enabled_modules, (str, bytes)):
        raise ValueError("enabled_modules must be a list")
    if not isinstance(module_configs, Sequence) or isinstance(module_configs, (str, bytes)):
        raise ValueError("module_configs must be a list")
    if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes)):
        raise ValueError("symbols must be a list")
    return AnalysisEngineConfig(
        enabled=enabled,
        thresholds=_parse_thresholds(thresholds),
        enabled_modules=[_require_str(item, "enabled_modules") for item in enabled_modules],
        module_configs=_parse_module_configs(module_configs),
        symbols=_parse_symbol_configs(symbols),
    )


def _parse_thresholds(data: Mapping[str, object]) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not key:
            raise ValueError("threshold keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"threshold {key} must be a number")
        thresholds[key] = float(value)
    return thresholds


def _parse_module_configs(items: Sequence[object]) -> tuple[ModuleConfig, ...]:
    configs: list[ModuleConfig] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("module_configs entries must be mappings")
        _reject_unknown(item, _MODULE_CONFIG_KEYS, "module_config")
        module_id = item.get("module_id")
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("module_config.module_id must be set")
        config = item.get("config")
        if config is not None and not isinstance(config, Mapping):
            raise ValueError("module_config.config must be a mapping if provided")
        configs.append(ModuleConfig(module_id=module_id, config=config))
    return tuple(configs)


def _parse_symbol_configs(items: Sequence[object]) -> tuple[SymbolConfig, ...]:
    configs: list[SymbolConfig] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("symbols entries must be mappings")
        _reject_unknown(item, _SYMBOL_CONFIG_KEYS, "symbol")
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be set in symbols")
        enabled_modules = item.get("enabled_modules")
        if not isinstance(enabled_modules, Sequence) or isinstance(enabled_modules, (str, bytes)):
            raise ValueError("symbol.enabled_modules must be a list")
        configs.append(
            SymbolConfig(
                symbol=symbol,
                enabled_modules=[
                    _require_str(val, "symbol.enabled_modules") for val in enabled_modules
                ],
            )
        )
    return tuple(configs)


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} entries must be non-empty strings")
    return value


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
