# Regime Engine — Task Plan

## Phase 0 — Data Contracts & Snapshot Builder

- [x] Define all snapshot dataclasses
- [x] Enforce 3m timestamp alignment
- [x] Explicit missing-data handling
- [x] Build snapshot builder (Binance REST + WS)
- [x] Snapshot serialization for replay

---

## Phase 1 — Feature Library

- [x] OI slope and acceleration
- [x] Funding level, slope, z-score
- [x] ATR and range expansion
- [x] CVD efficiency metrics
- [x] Acceptance score
- [x] Sweep score
- [x] Relative strength and breadth
- [x] Rolling normalization framework
- [x] Unit tests per feature

---

## Phase 2 — Regime Taxonomy & Scoring

- [x] Define Regime enum
- [x] Define RegimeScore model
- [x] Scoring stubs per regime
- [x] Contributor string generation

---

## Phase 3 — Hard Veto Logic

- [x] Weighted scoring logic
- [x] Veto rule framework
- [x] Encode core truth constraints
- [x] Veto logging

---

## Phase 4 — Resolution & Confidence

- [x] Regime ranking logic
- [x] Confidence calculation

---

## Phase 5 — Confidence Synthesis

- [x] Pillar grouping
- [x] Pillar agreement scoring
- [x] Confidence synthesis
- [x] Confidence explainability breakdown

---

## Phase 6 — Explainability

- [x] Driver extraction
- [x] Invalidation rule generation
- [x] Permission mapping
- [x] Enforce non-empty explainability fields

---

## Phase 7 — Hysteresis & Memory

- [x] Stability inputs
- [x] Regime persistence tracking
- [x] Flip threshold logic
- [x] Confidence decay

---

## Phase 8 — Logging & Evaluation Harness

- [ ] JSONL regime logs
- [ ] Snapshot replay runner
- [ ] Regime flip statistics
- [ ] Forward return analysis
- [ ] Regime expectancy report

---

## Phase 9 — Integration Readiness

- [ ] Stable RegimeOutput API
- [ ] State Gate compatibility check
- [ ] Pattern layer dependency audit
- [ ] Documentation pass
