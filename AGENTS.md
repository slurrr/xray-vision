# AGENTS.md — Repository-Level Rules

This file defines **repository-wide, non-semantic constraints**
for all non-human contributors (e.g., Codex, automation).

Subsystem-specific rules live in each directory’s `AGENTS.md`
and **override this file**.

If rules conflict, the **closest AGENTS.md in the directory tree wins**.

---

## Repository Identity

This is a **multi-layer mono-repo** for the xray-vision system.

Each top-level subsystem is:
- Independently governed
- Independently spec’d
- Independently evolvable

No subsystem is authoritative outside its scope.

---

## Scope Discipline (Mandatory)

- Changes must be limited to the active subsystem
- Cross-subsystem edits require explicit instruction
- Files may not be moved across subsystem boundaries casually

If unsure, stop.

---

## Architectural Authority

- High-level system intent is documented in:
  - `ARCHITECTURE_NEXT_LAYERS.md`
- Subsystem behavior is defined by:
  - `spec.md` within that subsystem

If code conflicts with a spec, the spec wins.

---

## Development Environment (Invariant)

- A local virtual environment at `.venv/` is mandatory
- All tooling must run inside the active `.venv`
- Install the package in editable mode before development:
  - `pip install -e .`

Do not modify `sys.path` or bypass the environment.

---

## Change Discipline

- No speculative refactors
- No “helpful” generalizations
- No semantic interpretation without a spec change

When rules are unclear, do not guess.

---

## Final Rule

This file sets **guardrails, not logic**.

All domain rules belong in subsystem-level `AGENTS.md`.
