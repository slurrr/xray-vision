from __future__ import annotations

from typing import TYPE_CHECKING

from regime_engine.contracts.snapshots import RegimeInputSnapshot

if TYPE_CHECKING:
    from regime_engine.scoring.types import UnweightedScores, VetoedScores


def apply_vetoes(unweighted: UnweightedScores, snapshot: RegimeInputSnapshot) -> VetoedScores:
    from regime_engine.veto import rules as veto_rules
    from regime_engine.scoring.types import VetoedScores

    vetoes = []
    for rule in veto_rules.rule_registry():
        vetoes.extend(rule(snapshot, list(unweighted.scores)))
    return VetoedScores(scores=list(unweighted.scores), vetoes=vetoes)
