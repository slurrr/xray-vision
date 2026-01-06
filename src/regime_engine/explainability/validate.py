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
    # TEMPORARY: allow empty invalidations while veto rules are stubbed.
    if invalidations is None:
        missing.append("invalidations")
    if not permissions:
        missing.append("permissions")
    if missing:
        raise ExplainabilityValidationError(
            "Explainability validation failed: " + ", ".join(missing)
        )

    if any(
        not isinstance(invalidation, str) or not invalidation for invalidation in invalidations
    ):
        raise ExplainabilityValidationError(
            "Explainability validation failed: invalidations"
        )
