from __future__ import annotations


CONTRIBUTOR_DRIVERS: dict[str, str] = {
    "context.alt_breadth": "Context alt breadth",
    "context.beta_to_btc": "Context beta to BTC",
    "context.rs_vs_btc": "Context relative strength vs BTC",
    "derivatives.funding_level": "Derivatives funding level",
    "derivatives.funding_slope": "Derivatives funding slope",
    "derivatives.funding_zscore": "Derivatives funding z-score",
    "derivatives.oi_acceleration": "Derivatives OI acceleration",
    "derivatives.oi_slope_med": "Derivatives OI slope medium",
    "derivatives.oi_slope_short": "Derivatives OI slope short",
    "flow.aggressive_volume_ratio": "Flow aggressive volume ratio",
    "flow.cvd_efficiency": "Flow CVD efficiency",
    "flow.cvd_slope": "Flow CVD slope",
    "market.acceptance_score": "Market acceptance score",
    "market.atr_zscore": "Market ATR z-score",
    "market.range_expansion": "Market range expansion",
    "market.sweep_score": "Market sweep score",
}


def drivers_from_contributors(contributors: list[str]) -> list[str]:
    drivers: list[str] = []
    seen: set[str] = set()
    for contributor in contributors:
        driver = CONTRIBUTOR_DRIVERS.get(contributor, contributor)
        if driver in seen:
            continue
        seen.add(driver)
        drivers.append(driver)
    return drivers
