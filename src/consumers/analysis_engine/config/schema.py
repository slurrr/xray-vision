from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from consumers.analysis_engine.registry import ModuleRegistry


@dataclass(frozen=True)
class ModuleConfig:
    module_id: str
    config: Mapping[str, object] | None


@dataclass(frozen=True)
class SymbolConfig:
    symbol: str
    enabled_modules: Sequence[str]


@dataclass(frozen=True)
class AnalysisEngineConfig:
    enabled: bool
    thresholds: Mapping[str, float]
    enabled_modules: Sequence[str]
    module_configs: Sequence[ModuleConfig]
    symbols: Sequence[SymbolConfig]


def validate_config(config: AnalysisEngineConfig, registry: ModuleRegistry) -> None:
    _validate_enabled_modules(config.enabled_modules, registry)
    _validate_module_configs(config.module_configs, registry)
    _validate_symbol_configs(config.symbols, registry)
    _validate_thresholds(config.thresholds)


def _validate_enabled_modules(enabled_modules: Sequence[str], registry: ModuleRegistry) -> None:
    for module_id in enabled_modules:
        if module_id not in registry.modules:
            raise ValueError(f"unknown module_id in enabled_modules: {module_id}")


def _validate_module_configs(configs: Sequence[ModuleConfig], registry: ModuleRegistry) -> None:
    seen: set[str] = set()
    for module_config in configs:
        if module_config.module_id not in registry.modules:
            raise ValueError(f"unknown module_id in module_configs: {module_config.module_id}")
        if module_config.module_id in seen:
            raise ValueError(f"duplicate module_config for {module_config.module_id}")
        seen.add(module_config.module_id)
        if module_config.config is not None and not isinstance(module_config.config, Mapping):
            raise ValueError(
                f"module_config for {module_config.module_id} must be a mapping if provided"
            )


def _validate_symbol_configs(
    symbol_configs: Sequence[SymbolConfig], registry: ModuleRegistry
) -> None:
    seen_symbols: set[str] = set()
    for symbol_config in symbol_configs:
        if symbol_config.symbol in seen_symbols:
            raise ValueError(f"duplicate symbol entry: {symbol_config.symbol}")
        seen_symbols.add(symbol_config.symbol)
        for module_id in symbol_config.enabled_modules:
            if module_id not in registry.modules:
                raise ValueError(f"unknown module_id in symbol config: {module_id}")


def _validate_thresholds(thresholds: Mapping[str, float]) -> None:
    for key, value in thresholds.items():
        if not isinstance(key, str) or not key:
            raise ValueError("threshold keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"threshold {key} must be a number")
