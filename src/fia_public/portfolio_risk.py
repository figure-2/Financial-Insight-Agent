"""Ephemeral portfolio-risk calculations over caller-supplied aligned returns."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


class PortfolioRiskError(ValueError):
    pass


def calculate_portfolio_risk(
    weights: Mapping[str, float],
    daily_returns: Mapping[str, Sequence[float]],
    *,
    trading_days: int = 252,
) -> dict[str, object]:
    if not weights or set(weights) != set(daily_returns):
        raise PortfolioRiskError("ticker_contract_invalid")
    if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise PortfolioRiskError("weight_invalid")
    if not math.isclose(sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise PortfolioRiskError("weight_sum_invalid")
    lengths = {len(values) for values in daily_returns.values()}
    if len(lengths) != 1 or next(iter(lengths)) < 2:
        raise PortfolioRiskError("aligned_history_insufficient")
    if any(any(not math.isfinite(value) for value in values) for values in daily_returns.values()):
        raise PortfolioRiskError("return_invalid")

    tickers = tuple(sorted(weights))
    rows = list(zip(*(daily_returns[ticker] for ticker in tickers), strict=True))
    portfolio_returns = [
        sum(weights[ticker] * row[index] for index, ticker in enumerate(tickers)) for row in rows
    ]
    variance = _sample_variance(portfolio_returns)
    annualized_volatility = math.sqrt(max(variance, 0.0) * trading_days)
    covariance = {
        left: {
            right: _sample_covariance(daily_returns[left], daily_returns[right])
            for right in tickers
        }
        for left in tickers
    }
    contributions = {
        ticker: weights[ticker]
        * sum(weights[other] * covariance[ticker][other] for other in tickers)
        * trading_days
        for ticker in tickers
    }
    return {
        "status": "ready",
        "session_count": len(rows),
        "maximum_weight": max(weights.values()),
        "hhi": sum(weight * weight for weight in weights.values()),
        "annualized_volatility": annualized_volatility,
        "annualized_variance_contributions": contributions,
        "trading_days_assumption": trading_days,
        "persistence": "none",
    }


def _sample_variance(values: Sequence[float]) -> float:
    return _sample_covariance(values, values)


def _sample_covariance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise PortfolioRiskError("aligned_history_insufficient")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    return sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True)) / (
        len(left) - 1
    )
