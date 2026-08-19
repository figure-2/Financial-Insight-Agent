"""Deterministic Market Evidence over validated caller-supplied OHLCV rows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .contracts import stable_hash


class MarketPipelineError(ValueError):
    """Raised when market rows violate identity or time-series contracts."""


@dataclass(frozen=True)
class OhlcvRow:
    session_date: date
    ticker: str
    open: str
    high: str
    low: str
    close: str
    volume: int


@dataclass(frozen=True)
class MarketEvidence:
    evidence_id: str
    company_id: str
    ticker: str
    as_of: str
    session_count: int
    dataset_hash: str
    return_20_sessions: float
    return_60_sessions: float
    annualized_volatility: float
    sma_20: str
    sma_60: str


def build_market_evidence(
    *,
    company_id: str,
    ticker: str,
    rows: tuple[OhlcvRow, ...],
    trading_days: int = 252,
) -> MarketEvidence:
    if company_id != f"krx:{ticker}" or not ticker.isdigit() or len(ticker) != 6:
        raise MarketPipelineError("market_company_binding_invalid")
    if not 61 <= len(rows) <= 66 or trading_days <= 0:
        raise MarketPipelineError("market_session_contract_invalid")

    canonical_rows: list[dict[str, object]] = []
    closes: list[Decimal] = []
    observed_dates: set[date] = set()
    previous_date: date | None = None
    for row in rows:
        if row.ticker != ticker or row.session_date in observed_dates:
            raise MarketPipelineError("market_row_identity_invalid")
        if previous_date is not None and row.session_date <= previous_date:
            raise MarketPipelineError("market_session_order_invalid")
        open_price, high, low, close = (
            _positive_decimal(row.open),
            _positive_decimal(row.high),
            _positive_decimal(row.low),
            _positive_decimal(row.close),
        )
        if high < max(open_price, close) or low > min(open_price, close) or high < low:
            raise MarketPipelineError("market_ohlc_relation_invalid")
        if isinstance(row.volume, bool) or row.volume < 0:
            raise MarketPipelineError("market_volume_invalid")
        canonical_rows.append(
            {
                "session_date": row.session_date.isoformat(),
                "ticker": row.ticker,
                "open": _decimal_text(open_price),
                "high": _decimal_text(high),
                "low": _decimal_text(low),
                "close": _decimal_text(close),
                "volume": row.volume,
            }
        )
        closes.append(close)
        observed_dates.add(row.session_date)
        previous_date = row.session_date

    daily_returns = [
        float(closes[index] / closes[index - 1] - 1)
        for index in range(1, len(closes))
    ]
    variance = _sample_variance(daily_returns)
    dataset_hash = stable_hash(canonical_rows)
    payload = {
        "company_id": company_id,
        "ticker": ticker,
        "as_of": rows[-1].session_date.isoformat(),
        "session_count": len(rows),
        "dataset_hash": dataset_hash,
        "return_20_sessions": float(closes[-1] / closes[-21] - 1),
        "return_60_sessions": float(closes[-1] / closes[-61] - 1),
        "annualized_volatility": math.sqrt(max(variance, 0.0) * trading_days),
        "sma_20": _decimal_text(sum(closes[-20:]) / Decimal(20)),
        "sma_60": _decimal_text(sum(closes[-60:]) / Decimal(60)),
    }
    return MarketEvidence(evidence_id=stable_hash(payload), **payload)


def _positive_decimal(value: str) -> Decimal:
    try:
        number = Decimal(value.replace(",", ""))
    except (AttributeError, InvalidOperation) as exc:
        raise MarketPipelineError("market_price_invalid") from exc
    if not number.is_finite() or number <= 0:
        raise MarketPipelineError("market_price_invalid")
    return number


def _decimal_text(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _sample_variance(values: list[float]) -> float:
    if len(values) < 2 or any(not math.isfinite(value) for value in values):
        raise MarketPipelineError("market_return_series_invalid")
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)
