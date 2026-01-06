import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from market_data.config import BackpressureConfig
from market_data.contracts import EVENT_TYPE_REQUIRED_NORMALIZED_KEYS, EVENT_TYPES, SCHEMA_NAME, SCHEMA_VERSION
from market_data.decoder import decode_and_ingest
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline
from market_data.serialization import deserialize_event, serialize_event


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event, *, block: bool, timeout_ms: int | None) -> None:
        self.events.append(event)


class TestMarketDataSafety(unittest.TestCase):
    def _pipeline(self) -> IngestionPipeline:
        return IngestionPipeline(
            sink=RecordingSink(),
            backpressure=BackpressureConfig(policy="block", max_pending=1, max_block_ms=50),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 500,
        )

    def test_envelope_and_required_normalized_keys(self) -> None:
        payloads = {
            "TradeTick": {"price": 1.0, "quantity": 2.0, "side": "buy"},
            "BookTop": {
                "best_bid_price": 1.0,
                "best_bid_quantity": 2.0,
                "best_ask_price": 3.0,
                "best_ask_quantity": 4.0,
            },
            "BookDelta": {"bids": [[1.0, 2.0]], "asks": [[3.0, 4.0]]},
            "Candle": {
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
                "interval_ms": 60000,
            },
            "FundingRate": {"funding_rate": 0.01},
            "OpenInterest": {"open_interest": 100.0},
            "MarkPrice": {"mark_price": 1.23},
            "IndexPrice": {"index_price": 1.25},
            "LiquidationPrint": {"price": 1.0, "quantity": 2.0, "side": "sell"},
            "SnapshotInputs": {"timestamp_ms": 123, "market": {}},
        }

        pipeline = self._pipeline()
        for event_type in EVENT_TYPES:
            if event_type == "DecodeFailure":
                continue
            raw_payload = _to_bytes(payloads[event_type])
            event = decode_and_ingest(
                pipeline=pipeline,
                event_type=event_type,
                source_id="test-source",
                symbol="TEST",
                exchange_ts_ms=1,
                raw_payload=raw_payload,
                payload_content_type="application/json",
            )

            self.assertEqual(event.schema, SCHEMA_NAME)
            self.assertEqual(event.schema_version, SCHEMA_VERSION)
            self.assertEqual(event.event_type, event_type)
            self.assertEqual(event.source_id, "test-source")
            self.assertEqual(event.symbol, "TEST")
            self.assertEqual(event.recv_ts_ms, 500)
            self.assertEqual(event.raw_payload, raw_payload)

            required_keys = EVENT_TYPE_REQUIRED_NORMALIZED_KEYS[event_type]
            self.assertTrue(required_keys.issubset(event.normalized.keys()))

    def test_decode_failure_on_malformed_input(self) -> None:
        pipeline = self._pipeline()
        raw_payload = b"{bad-json}"
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=raw_payload,
            payload_content_type="application/json",
        )

        self.assertEqual(event.event_type, "DecodeFailure")
        self.assertEqual(event.raw_payload, raw_payload)

    def test_event_is_immutable_and_serialization_is_stable(self) -> None:
        pipeline = self._pipeline()
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=b"{\"price\": 1, \"quantity\": 1, \"side\": null}",
            payload_content_type="application/json",
        )

        with self.assertRaises(FrozenInstanceError):
            event.symbol = "OTHER"  # type: ignore[misc]

        serialized = serialize_event(event)
        self.assertEqual(serialized, serialize_event(event))
        deserialized = deserialize_event(serialized)
        self.assertEqual(deserialized["schema"], SCHEMA_NAME)
        self.assertIn("raw_payload_encoding", deserialized)

    def test_no_regime_engine_imports(self) -> None:
        root = Path(__file__).resolve().parents[3] / "src" / "market_data"
        for path in root.rglob("*.py"):
            contents = path.read_text(encoding="utf-8")
            self.assertNotIn("regime_engine", contents, msg=f"regime_engine found in {path}")


def _to_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
