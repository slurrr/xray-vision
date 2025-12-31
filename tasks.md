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

- [ ] Define Regime enum
- [ ] Define RegimeScore model
- [ ] Scoring stubs per regime
- [ ] Weighted scoring logic
- [ ] Contributor string generation

---

## Phase 3 — Hard Veto Logic

- [ ] Veto rule framework
- [ ] Encode core truth constraints
- [ ] Veto logging

---

## Phase 4 — Resolution & Confidence

- [ ] Regime ranking logic
- [ ] Confidence calculation
- [ ] Pillar agreement scoring
- [ ] Stability inputs

---

## Phase 5 — Explainability

- [ ] Driver extraction
- [ ] Invalidation rule generation
- [ ] Permission mapping
- [ ] Enforce non-empty explainability fields

---

## Phase 6 — Hysteresis & Memory

- [ ] Regime persistence tracking
- [ ] Flip threshold logic
- [ ] Confidence decay

---

## Phase 7 — Logging & Evaluation Harness

- [ ] JSONL regime logs
- [ ] Snapshot replay runner
- [ ] Regime flip statistics
- [ ] Forward return analysis
- [ ] Regime expectancy report

---

## Phase 8 — Integration Readiness

- [ ] Stable RegimeOutput API
- [ ] State Gate compatibility check
- [ ] Pattern layer dependency audit
- [ ] Documentation pass
