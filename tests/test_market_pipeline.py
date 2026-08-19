from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.market_pipeline import (  # noqa: E402
    MarketPipelineError,
    OhlcvRow,
    build_market_evidence,
)


def sample_rows() -> tuple[OhlcvRow, ...]:
    start = date(2026, 5, 1)
    return tuple(
        OhlcvRow(
            session_date=start + timedelta(days=index),
            ticker="000001",
            open=str(100 + index),
            high=str(102 + index),
            low=str(99 + index),
            close=str(101 + index),
            volume=1000 + index,
        )
        for index in range(61)
    )


class MarketPipelineTests(unittest.TestCase):
    def test_valid_rows_create_deterministic_market_evidence(self) -> None:
        rows = sample_rows()
        first = build_market_evidence(company_id="krx:000001", ticker="000001", rows=rows)
        second = build_market_evidence(company_id="krx:000001", ticker="000001", rows=rows)
        self.assertEqual(first, second)
        self.assertEqual(first.session_count, 61)
        self.assertEqual(first.as_of, rows[-1].session_date.isoformat())
        self.assertGreater(first.return_60_sessions, 0)

    def test_company_and_ticker_mismatch_fail_closed(self) -> None:
        with self.assertRaises(MarketPipelineError):
            build_market_evidence(
                company_id="krx:000002",
                ticker="000001",
                rows=sample_rows(),
            )
        rows = list(sample_rows())
        rows[10] = replace(rows[10], ticker="000002")
        with self.assertRaises(MarketPipelineError):
            build_market_evidence(
                company_id="krx:000001",
                ticker="000001",
                rows=tuple(rows),
            )

    def test_order_duplicate_and_ohlc_relation_fail_closed(self) -> None:
        rows = list(sample_rows())
        rows[1] = replace(rows[1], session_date=rows[0].session_date)
        with self.assertRaises(MarketPipelineError):
            build_market_evidence(
                company_id="krx:000001",
                ticker="000001",
                rows=tuple(rows),
            )
        rows = list(sample_rows())
        rows[5] = replace(rows[5], high="1")
        with self.assertRaises(MarketPipelineError):
            build_market_evidence(
                company_id="krx:000001",
                ticker="000001",
                rows=tuple(rows),
            )

    def test_session_count_outside_61_to_66_is_rejected(self) -> None:
        with self.assertRaises(MarketPipelineError):
            build_market_evidence(
                company_id="krx:000001",
                ticker="000001",
                rows=sample_rows()[:60],
            )


if __name__ == "__main__":
    unittest.main()
