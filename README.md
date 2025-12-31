# xray-vision — Regime Engine

The Regime Engine is the truth layer of a crypto scanner. It classifies why price is
moving, determines allowed behaviors, and exposes invalidations. All downstream
layers depend on its outputs and may not recompute regime logic.

Non-goals:
- Pattern detection
- Trade signals
- Execution logic
- Strategy assumptions

Phase discipline:
- Follow `tasks.md` strictly in order.
- Contracts come first. Do not implement features/scoring/veto/hysteresis logic
  until Phase 0 contracts are complete and frozen.

Determinism requirements:
- Frozen dataclasses for snapshots and outputs
- Explicit missing data representation (never silent)
- Snapshot serialization suitable for replay

