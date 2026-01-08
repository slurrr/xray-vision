# XRAY-VISION — Composer & Belief Architecture Planning Document

## Purpose

This document captures the resolved architectural direction for xray-vision at the current inflection point. It defines how the system transitions from a classifier-shaped regime engine to a belief-driven regime system, while preserving determinism, frozen contracts discipline, and replay guarantees.

This document is planning input, not a spec.
It exists to drive the creation of:

a new Composer subsystem

additive contracts for belief-driven inference

minimal semantic updates to the Regime Engine

No existing frozen contracts are to be modified in this phase.

### Problem Statement

The current system has:

deterministic ingestion (market_data)

deterministic orchestration (orchestrator)

an implemented but not fully wired Regime Engine

no subsystem responsible for computing indicators or assembling engine-ready inputs

The Regime Engine was originally conceived as a classifier, consuming dense snapshots of pre-computed features. Through design iteration, it became clear the system wants to be a belief engine:

regime = derived label

regime state = belief distribution with memory and hysteresis

inference operates on opinions / evidence, not raw features

Raw payloads cannot carry belief inputs.
Feature math cannot live in ingestion.
Inference cannot compute indicators.
Analysis is gated and non-authoritative.

A new layer is required to compose belief-ready inputs deterministically.

### Core Architectural Resolution

Key Principle

Belief is not in the data. Belief is constructed.

Therefore:

belief inputs must be assembled

indicator math must occur before inference

inference must only operate on evidence and belief state

regime classification is a projection, not a parallel authority

## Composer Subsystem (New)

## Role

The Composer is a deterministic, stateless assembly layer that transforms raw market events into engine-ready inputs.

It is responsible for:

Computing features (numeric, descriptive)

Constructing evidence (opinionated, sparse)

Assembling immutable snapshots for inference

Guaranteeing replay equivalence

The Composer performs no inference, no belief updates, and no hysteresis.

## Types of Computation (Explicit Separation)

The system recognizes three distinct computation classes:

1. Feature Computation (Composer responsibility)

Indicators

Slopes, z-scores

Rolling stats

Ratios

Structure measurements

Properties:

deterministic

numeric

window-bounded state only

no interpretation

no belief

These live in a features/ module inside Composer.

2. Evidence Construction (Composer responsibility)

Interprets features

Emits opinions (direction, strength, confidence)

Stateless

Deterministic

Examples:

Classical regime classification opinion

Flow pressure opinion

Participation expansion/contraction opinion

These live in an evidence/ module inside Composer.

3. Inference & Belief Update (Regime Engine responsibility)

Updates belief distribution

Applies hysteresis

Maintains memory

Produces regime state

The Regime Engine never computes indicators or interprets raw data.

## Regime vs Regime State (Resolved Semantics)

Regime

A label describing market structure under an interpretive lens

Stateless

Instantaneous

Can disagree across observers

Derived from belief (not stored)

Regime State

Probability distribution over regimes

Memory-bearing

Hysteretic

Sole authoritative state for inference

Anchor Regime = projection of Regime State (e.g. argmax belief).

Hysteresis (Clarified)

Hysteresis is not a wrapper on regime labels.

Hysteresis is:

inertia on belief updates

resistance to abrupt belief shifts

implemented inside the belief update loop

Dashboard outputs such as:

TRANSITIONING → TREND_UP (2 / 3)

represent sustained belief pressure, not label verification.

Regime Engine (Semantic Update Only)

The Regime Engine remains a single engine.

Internally it is conceptually split into:

Observers (stateless; emit evidence)

Belief Updater (stateful; hysteretic)

Projection (belief → outputs)

Classical regime logic is treated as an observer opinion, not truth.

The Regime Engine:

consumes EvidenceSnapshot

updates RegimeState

emits projected outputs for downstream systems

No dual authority exists.

Composer Outputs (Additive Contracts)

The Composer will emit:

FeatureSnapshot

Dense numeric features

Deterministic

Replayable

Used by evidence observers

EvidenceSnapshot

Sparse list of opinions

Each opinion has:

type

direction

strength

confidence

source (for explainability)

Only EvidenceSnapshot is consumed by the belief updater.

Integration with Existing System

market_data: unchanged

orchestrator: unchanged (invokes engine with composed inputs)

state_gate: unchanged semantics (operates on engine outputs)

analysis_engine: unchanged (consumer, gated, non-authoritative)

dashboards: unchanged UX (now has clean belief semantics)

All changes are additive.

Naming & Structure Guidance

Composer should be a top-level subsystem with internal factoring:

composer/
├── AGENTS.md
├── contracts/
├── composer.py        # orchestration / assembly
├── features/          # all indicator math
├── evidence/          # all opinion construction
└── tests/

No additional top-level subsystem is required.

What This Planning Phase Must Produce

This document should be used to generate:

src/composer/AGENTS.md

Planning/composer/spec.md

Planning/composer/tasks.md

Additive contracts:

FeatureSnapshot

EvidenceSnapshot

EvidenceOpinion

RegimeState

Minimal semantic updates to Regime Engine documentation (no refactors yet)

Explicit Non-Goals for This Phase

No deletion of existing contracts

No refactoring of Regime Engine logic

No optimization

No Bayesian math implementation

No wiring to orchestrator yet

No analysis logic

This phase names and freezes what did not previously exist.

Anchoring Statement

The system is not transitioning from “simple” to “complex.”

It is transitioning from:

belief implicit in hysteresis wrappers
→ belief as a first-class, authoritative state

Once belief is named, composed, and isolated, every downstream decision becomes obvious.

End of Planning Document