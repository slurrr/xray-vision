"""
Public, stable Regime Engine API.

Hard rule: no regime logic lives here. This module validates inputs/outputs
and orchestrates calls into the internal pipeline.
"""

from __future__ import annotations

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.hysteresis import HysteresisConfig, HysteresisDecision, HysteresisStore, process_output
from regime_engine.pipeline import run_pipeline


def run(snapshot: RegimeInputSnapshot) -> RegimeOutput:
    return run_pipeline(snapshot)


def run_with_hysteresis(
    snapshot: RegimeInputSnapshot,
    state: HysteresisStore,
    config: HysteresisConfig | None = None,
) -> HysteresisDecision:
    output = run(snapshot)
    return process_output(output, store=state, config=config)
