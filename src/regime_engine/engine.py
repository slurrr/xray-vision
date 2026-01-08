"""
Public, stable Regime Engine API.

Hard rule: no regime logic lives here. This module validates inputs/outputs
and orchestrates calls into the internal pipeline.
"""

from __future__ import annotations

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.hysteresis import (
    HysteresisConfig,
    HysteresisState,
    HysteresisStore,
    process_state,
)
from regime_engine.pipeline import run_pipeline, run_pipeline_with_state


def run(snapshot: RegimeInputSnapshot) -> RegimeOutput:
    return run_pipeline(snapshot)


def run_with_hysteresis(
    snapshot: RegimeInputSnapshot,
    state: HysteresisStore,
    config: HysteresisConfig | None = None,
) -> HysteresisState:
    _output, regime_state = run_pipeline_with_state(snapshot)
    return process_state(regime_state, store=state, config=config)
