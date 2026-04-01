"""Technical indicator functions operating on pandas Series."""

import pandas as pd
import numpy as np


# ─── Basic Moving Averages ───────────────────────────────────────────

def MA(series: pd.Series, n: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=int(n), min_periods=int(n)).mean()


def EMA(series: pd.Series, n: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=int(n), adjust=False).mean()


def SMA(series: pd.Series, n: int, m: int = 1) -> pd.Series:
    """TDX-style SMA: Y = (X*M + Y'*(N-M)) / N."""
    n, m = int(n), int(m)
    result = series.copy().astype(float)
    result.iloc[0] = series.iloc[0]
    for i in range(1, len(series)):
        val = series.iloc[i]
        if pd.isna(val):
            val = 0
        result.iloc[i] = (val * m + result.iloc[i - 1] * (n - m)) / n
    return result


# ─── Reference Functions ─────────────────────────────────────────────

def REF(series: pd.Series, n: int) -> pd.Series:
    """Reference N periods ago."""
    return series.shift(int(n))


# ─── Cross Functions ─────────────────────────────────────────────────

def CROSS(a: pd.Series, b) -> pd.Series:
    """True when A crosses above B."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def LONGCROSS(a: pd.Series, b, n: int) -> pd.Series:
    """A below B for N periods then crosses above."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    n = int(n)
    below = a < b
    consecutive = below.rolling(window=n, min_periods=n).sum() == n
    cross_up = CROSS(a, b)
    return cross_up & consecutive.shift(1)


# ─── Statistical Functions ───────────────────────────────────────────

def HHV(series: pd.Series, n: int) -> pd.Series:
    """Highest value in last N periods."""
    return series.rolling(window=int(n), min_periods=1).max()


def LLV(series: pd.Series, n: int) -> pd.Series:
    """Lowest value in last N periods."""
    return series.rolling(window=int(n), min_periods=1).min()


def COUNT(cond: pd.Series, n: int) -> pd.Series:
    """Count True values in last N periods."""
    return cond.astype(float).rolling(window=int(n), min_periods=1).sum()


def SUM_N(series: pd.Series, n: int) -> pd.Series:
    """Sum over last N periods."""
    return series.rolling(window=int(n), min_periods=1).sum()


def STD(series: pd.Series, n: int) -> pd.Series:
    """Standard deviation over N periods."""
    return series.rolling(window=int(n), min_periods=int(n)).std()


def AVEDEV(series: pd.Series, n: int) -> pd.Series:
    """Average absolute deviation over N periods."""
    n = int(n)
    return series.rolling(window=n).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )


# ─── Pattern Functions ───────────────────────────────────────────────

def BARSLAST(cond: pd.Series) -> pd.Series:
    """Bars since last True."""
    result = pd.Series(np.nan, index=cond.index)
    count = 0
    for i in range(len(cond)):
        if cond.iloc[i]:
            count = 0
        result.iloc[i] = count
        count += 1
    return result


def EVERY(cond: pd.Series, n: int) -> pd.Series:
    """True if condition True for all of last N periods."""
    n = int(n)
    return cond.astype(float).rolling(window=n, min_periods=n).sum() == n


def EXIST(cond: pd.Series, n: int) -> pd.Series:
    """True if condition True at least once in last N periods."""
    n = int(n)
    return cond.astype(float).rolling(window=n, min_periods=1).sum() > 0


# ─── Math Functions ──────────────────────────────────────────────────

def ABS_S(series) -> pd.Series:
    """Absolute value."""
    if isinstance(series, pd.Series):
        return series.abs()
    return abs(series)


def MAX_S(a, b):
    """Element-wise maximum."""
    if isinstance(a, pd.Series) and isinstance(b, pd.Series):
        return pd.concat([a, b], axis=1).max(axis=1)
    return np.maximum(a, b)


def MIN_S(a, b):
    """Element-wise minimum."""
    if isinstance(a, pd.Series) and isinstance(b, pd.Series):
        return pd.concat([a, b], axis=1).min(axis=1)
    return np.minimum(a, b)


def SQRT_S(series):
    """Square root."""
    return np.sqrt(series)


def IF_S(cond, a, b):
    """Conditional: IF(cond, a, b)."""
    if isinstance(cond, pd.Series):
        return pd.Series(np.where(cond, a, b), index=cond.index)
    return a if cond else b


def POW_S(a, b):
    """Power function."""
    return np.power(a, b)


# ─── Composite Indicators ───────────────────────────────────────────

def MACD(close: pd.Series, short=12, long=26, mid=9):
    """MACD indicator. Returns (DIF, DEA, MACD_HIST)."""
    short, long, mid = int(short), int(long), int(mid)
    dif = EMA(close, short) - EMA(close, long)
    dea = EMA(dif, mid)
    macd_hist = (dif - dea) * 2
    return dif, dea, macd_hist


def KDJ(close, high, low, n=9, m1=3, m2=3):
    """KDJ indicator. Returns (K, D, J)."""
    n, m1, m2 = int(n), int(m1), int(m2)
    llv = LLV(low, n)
    hhv = HHV(high, n)
    denom = hhv - llv
    denom = denom.replace(0, np.nan)
    rsv = (close - llv) / denom * 100
    rsv = rsv.fillna(50)
    k = SMA(rsv, m1, 1)
    d = SMA(k, m2, 1)
    j = 3 * k - 2 * d
    return k, d, j


def RSI(close: pd.Series, n: int = 14):
    """RSI indicator."""
    n = int(n)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = SMA(gain, n, 1)
    avg_loss = SMA(loss, n, 1)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def BOLL(close: pd.Series, n: int = 20, k: float = 2):
    """Bollinger Bands. Returns (UPPER, MID, LOWER)."""
    n = int(n)
    mid = MA(close, n)
    std = STD(close, n)
    upper = mid + k * std
    lower = mid - k * std
    return upper, mid, lower


def WR(close, high, low, n=14):
    """Williams %R."""
    n = int(n)
    hhv = HHV(high, n)
    llv = LLV(low, n)
    return (hhv - close) / (hhv - llv).replace(0, np.nan) * 100


def ATR(close, high, low, n=14):
    """Average True Range."""
    n = int(n)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return MA(tr, n)
