import unittest

from composer.contracts.evidence_opinion import EvidenceOpinion
from composer.contracts.feature_snapshot import (
    FEATURE_KEYS_V1,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    FeatureSnapshot,
)
from composer.contracts.ordering import order_evidence_opinions
from composer.evidence.compute import compute_evidence_snapshot
from composer.evidence.observers import OBSERVERS_V1


def _feature_snapshot_with_values() -> FeatureSnapshot:
    features = {key: 1.0 for key in FEATURE_KEYS_V1}
    return FeatureSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol="TEST",
        engine_timestamp_ms=100,
        features=features,
    )


class TestEvidenceSnapshot(unittest.TestCase):
    def test_evidence_snapshot_is_deterministic(self) -> None:
        snapshot = _feature_snapshot_with_values()
        first = compute_evidence_snapshot(snapshot)
        second = compute_evidence_snapshot(snapshot)
        self.assertEqual(first, second)

    def test_evidence_snapshot_ordering(self) -> None:
        snapshot = _feature_snapshot_with_values()
        evidence = compute_evidence_snapshot(snapshot)
        types = [opinion.type for opinion in evidence.opinions]
        self.assertEqual(
            types,
            sorted(types),
        )

    def test_observers_are_stateless(self) -> None:
        snapshot = _feature_snapshot_with_values()
        for observer in OBSERVERS_V1:
            with self.subTest(observer_id=observer.observer_id):
                first = observer.emit(snapshot)
                second = observer.emit(snapshot)
                self.assertEqual(first, second)

    def test_opinion_ordering_rule(self) -> None:
        opinions = [
            EvidenceOpinion(
                type="B",
                direction="DOWN",
                strength=0.5,
                confidence=0.2,
                source="b",
            ),
            EvidenceOpinion(
                type="A",
                direction="UP",
                strength=0.2,
                confidence=0.9,
                source="a",
            ),
            EvidenceOpinion(
                type="A",
                direction="DOWN",
                strength=0.9,
                confidence=0.1,
                source="a",
            ),
            EvidenceOpinion(
                type="A",
                direction="DOWN",
                strength=0.9,
                confidence=0.8,
                source="a",
            ),
        ]
        ordered = order_evidence_opinions(opinions)
        self.assertEqual(
            [opinion.type for opinion in ordered],
            ["A", "A", "A", "B"],
        )
        self.assertEqual(
            [opinion.confidence for opinion in ordered[:2]],
            [0.8, 0.1],
        )


if __name__ == "__main__":
    unittest.main()
