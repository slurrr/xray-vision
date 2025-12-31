import unittest

from regime_engine.snapshot_builder.builder import assert_timestamp_aligned


class TestTimestampAlignment(unittest.TestCase):
    def test_timestamp_alignment_accepts_epoch_aligned_3m(self) -> None:
        assert_timestamp_aligned(0)
        assert_timestamp_aligned(180_000)
        assert_timestamp_aligned(360_000)

    def test_timestamp_alignment_rejects_non_aligned(self) -> None:
        with self.assertRaises(ValueError):
            assert_timestamp_aligned(1)

        with self.assertRaises(ValueError):
            assert_timestamp_aligned(179_999)


if __name__ == "__main__":
    unittest.main()
