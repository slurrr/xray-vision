from __future__ import annotations

from regime_engine.contracts.regimes import RegimeScore


class ExplainabilityValidationError(ValueError):
    pass


def validate_explainability(
    winner: RegimeScore | None,
    drivers: list[str],
    invalidations: list[str],
    permissions: list[str],
) -> None:
    missing: list[str] = []
    if winner is None:
        missing.append("winner")
    if not drivers:
        missing.append("drivers")
    if not invalidations:
        missing.append("invalidations")
    if not permissions:
        missing.append("permissions")
    if missing:
        raise ExplainabilityValidationError(
            "Explainability validation failed: " + ", ".join(missing)
        )
