from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class StructuredLogger(Protocol):
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None: ...


@dataclass(frozen=True)
class StdlibLogger:
    logger: logging.Logger

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.logger.log(level, message, extra={"fields": dict(fields)})


@dataclass(frozen=True)
class NullLogger:
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        return None


@dataclass(frozen=True)
class Observability:
    logger: StructuredLogger

    def log_evidence_emitted(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        opinion_count: int,
        regimes: Sequence[str],
    ) -> None:
        self.logger.log(
            logging.INFO,
            "composer.evidence.emitted",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "opinion_count": opinion_count,
                "regimes": list(regimes),
            },
        )

    def log_opinion_provenance(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        opinion_count: int,
        opinions: Sequence[Mapping[str, object]],
        feature_digest: Mapping[str, object],
    ) -> None:
        self.logger.log(
            logging.INFO,
            "composer.evidence.provenance",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "opinion_count": opinion_count,
                "opinions": list(opinions),
                "feature_digest": dict(feature_digest),
            },
        )

    def log_embed_decision(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        opinion_count: int,
        written: bool,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "composer.evidence.embed",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "opinion_count": opinion_count,
                "written": written,
            },
        )


_OBSERVABILITY = Observability(logger=NullLogger())


def set_observability(observability: Observability) -> None:
    global _OBSERVABILITY
    _OBSERVABILITY = observability


def get_observability() -> Observability:
    return _OBSERVABILITY
