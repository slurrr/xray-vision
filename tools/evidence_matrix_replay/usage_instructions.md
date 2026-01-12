# xray-vision — Replay & Diff Cheatsheet

This cheatsheet documents how to use the replay tooling to freeze behavior,
re-run the system deterministically, and diff outputs across code changes.

---

## 1) Capture (Create a Baseline)

Freeze a live run into deterministic, replayable artifacts. **Add folder when invoking captures**

```bash
.venv/bin/python tools/evidence_matrix_replay/capture.py \
  --output-dir tools/evidence_matrix_replay/captures
```

Creates:
- `raw_market_events.jsonl`
- `orchestrator_events.jsonl`

Notes:
- Opt-in only
- Does not change runtime behavior
- Run once per baseline
- Baselines are immutable

---

## 2) Replay (Run Code Against Frozen Inputs)

Re-run the system offline using the captured artifacts.

### Cold replay (default)

```bash
.venv/bin/python tools/evidence_matrix_replay/replay.py \
  --input-dir tools/evidence_matrix_replay/captures \
  --output-dir tools/evidence_matrix_replay/replays/cold_baseline
```

### Warm replay (reuse hysteresis state)

```bash
.venv/bin/python tools/evidence_matrix_replay/replay.py \
  --input-dir tools/evidence_matrix_replay/captures \
  --output-dir tools/evidence_matrix_replay/replays/warm_baseline \
  --hysteresis-state-path /path/to/hysteresis_store.jsonl
  
```

Notes:
- No adapters
- No decoders
- No live data
- Same inputs, new code

---

## 3) Diff (Compare Outputs)

Compare two replay output directories.

```bash
.venv/bin/python tools/evidence_matrix_replay/diff.py \
  --baseline-dir tools/evidence_matrix_replay/replays \
  --candidate-dir tools/evidence_matrix_replay/replays
```

Interpretation:
- Identical → non-interfering change
- Different → intentional change or regression

---

## Recommended Workflow

1. Capture a baseline once
2. Replay baseline → save outputs
3. Change code
4. Replay same baseline → save outputs
5. Diff baseline vs candidate
6. Decide if changes are intended

---

## When to Re-Capture

Re-capture only when you intend to redefine “normal” behavior.

Examples:
- Major semantic upgrade
- New market regime definition
- New long-term baseline

Do NOT re-capture for:
- Refactors
- Bug fixes
- Legacy removal
- Performance changes

---

## Mental Model

Capture freezes **what happened**.  
Replay asks **what would happen now**.  
Diff shows **what changed**.
