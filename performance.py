"""Future return calculation and aggregate statistics."""

import numpy as np
import logging

logger = logging.getLogger(__name__)

HORIZONS = [3, 5, 10, 20]


def calculate_returns(df, screen_idx: int) -> dict:
    """Calculate future returns at each horizon from the screening date.

    Args:
        df: Stock DataFrame with 'close' column
        screen_idx: Index of the screening date row

    Returns:
        Dict with keys return_3d, return_5d, return_10d, return_20d (% values)
    """
    screen_price = float(df.iloc[screen_idx]["close"])
    results = {}

    for h in HORIZONS:
        future_idx = screen_idx + h
        if future_idx < len(df):
            future_price = float(df.iloc[future_idx]["close"])
            pct = (future_price - screen_price) / screen_price * 100
            results[f"return_{h}d"] = round(pct, 2)
        else:
            results[f"return_{h}d"] = None

    return results


def aggregate_stats(results: list) -> dict:
    """Compute aggregate statistics across all matched stocks.

    Args:
        results: List of dicts from calculate_returns

    Returns:
        Dict with avg, win_rate, max_gain, max_loss, median per horizon
    """
    stats = {}

    for h in HORIZONS:
        key = f"return_{h}d"
        values = [r[key] for r in results if r.get(key) is not None]

        if values:
            arr = np.array(values)
            stats[f"avg_{h}d"] = round(float(np.mean(arr)), 2)
            stats[f"median_{h}d"] = round(float(np.median(arr)), 2)
            stats[f"win_rate_{h}d"] = round(
                float(np.sum(arr > 0) / len(arr) * 100), 1
            )
            stats[f"max_gain_{h}d"] = round(float(np.max(arr)), 2)
            stats[f"max_loss_{h}d"] = round(float(np.min(arr)), 2)
            stats[f"std_{h}d"] = round(float(np.std(arr)), 2)
            stats[f"count_{h}d"] = len(values)
        else:
            stats[f"avg_{h}d"] = None
            stats[f"win_rate_{h}d"] = None
            stats[f"count_{h}d"] = 0

    return stats
