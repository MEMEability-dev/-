"""Future return calculation and aggregate statistics."""

import numpy as np
import logging

logger = logging.getLogger(__name__)

HORIZONS = [3, 5, 10]
MAX_GAIN_WINDOW = 15


def calculate_returns(df, screen_idx: int) -> dict:
    """Calculate future returns at each horizon from the screening date.

    Args:
        df: Stock DataFrame with 'close' column
        screen_idx: Index of the screening date row

    Returns:
        Dict with keys return_3d, return_5d, return_10d, return_max15d (% values)
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

    # Max gain within next 15 trading days using highest HIGH as sell point.
    start = screen_idx + 1
    end = min(len(df), screen_idx + MAX_GAIN_WINDOW + 1)
    if start < end:
        window_high = float(df.iloc[start:end]["high"].max())
        max_pct = (window_high - screen_price) / screen_price * 100
        results["return_max15d"] = round(max_pct, 2)
    else:
        results["return_max15d"] = None

    return results


def aggregate_stats(results: list) -> dict:
    """Compute aggregate statistics across all matched stocks.

    Args:
        results: List of dicts from calculate_returns

    Returns:
        Dict with avg, win_rate, max_gain, max_loss, median per horizon
    """
    stats = {}

    metric_defs = [(f"return_{h}d", f"{h}d") for h in HORIZONS]
    metric_defs.append(("return_max15d", "max15d"))

    for key, tag in metric_defs:
        values = [r[key] for r in results if r.get(key) is not None]

        if values:
            arr = np.array(values)
            stats[f"avg_{tag}"] = round(float(np.mean(arr)), 2)
            stats[f"median_{tag}"] = round(float(np.median(arr)), 2)
            stats[f"win_rate_{tag}"] = round(
                float(np.sum(arr > 0) / len(arr) * 100), 1
            )
            stats[f"max_gain_{tag}"] = round(float(np.max(arr)), 2)
            stats[f"max_loss_{tag}"] = round(float(np.min(arr)), 2)
            stats[f"std_{tag}"] = round(float(np.std(arr)), 2)
            stats[f"count_{tag}"] = len(values)
        else:
            stats[f"avg_{tag}"] = None
            stats[f"win_rate_{tag}"] = None
            stats[f"count_{tag}"] = 0

    return stats
