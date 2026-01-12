from __future__ import annotations

from dataclasses import dataclass

from orchestrator.buffer import RawInputBuffer


@dataclass(frozen=True)
class Cut:
    symbol: str
    cut_start_ingest_seq: int
    cut_end_ingest_seq: int
    cut_kind: str


class CutSelector:
    def __init__(self) -> None:
        self._last_end_by_symbol: dict[str, int] = {}

    def next_cut(
        self,
        *,
        buffer: RawInputBuffer,
        symbol: str,
        cut_end_ingest_seq: int,
        cut_kind: str,
    ) -> Cut:
        if cut_end_ingest_seq <= 0:
            raise ValueError("cut_end_ingest_seq must be > 0")
        last_end = self._last_end_by_symbol.get(symbol)
        start_seq = (last_end + 1) if last_end is not None else self._first_seq_for_symbol(
            buffer, symbol, cut_end_ingest_seq
        )
        if start_seq is None:
            raise ValueError("no buffered records available for symbol")
        if start_seq > cut_end_ingest_seq:
            raise ValueError("cut_start_ingest_seq must be <= cut_end_ingest_seq")
        self._last_end_by_symbol[symbol] = cut_end_ingest_seq
        return Cut(
            symbol=symbol,
            cut_start_ingest_seq=start_seq,
            cut_end_ingest_seq=cut_end_ingest_seq,
            cut_kind=cut_kind,
        )

    @staticmethod
    def latest_ingest_seq(buffer: RawInputBuffer) -> int | None:
        return buffer.last_ingest_seq()

    def min_consumed_ingest_seq(self) -> int | None:
        if not self._last_end_by_symbol:
            return None
        return min(self._last_end_by_symbol.values())

    @staticmethod
    def _first_seq_for_symbol(
        buffer: RawInputBuffer, symbol: str, cut_end_ingest_seq: int
    ) -> int | None:
        for record in buffer.range_by_seq(start_seq=1, end_seq=cut_end_ingest_seq):
            if record.event.symbol == symbol:
                return record.ingest_seq
        return None
