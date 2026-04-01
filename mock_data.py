"""Mock data generator for offline/sandbox operation."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib


MOCK_STOCKS = [
    ("000001", "平安银行"), ("000002", "万科A"), ("000063", "中兴通讯"),
    ("000333", "美的集团"), ("000538", "云南白药"), ("000651", "格力电器"),
    ("000725", "京东方A"), ("000858", "五粮液"), ("002024", "苏宁易购"),
    ("002142", "宁波银行"), ("002230", "科大讯飞"), ("002304", "洋河股份"),
    ("002415", "海康威视"), ("002594", "比亚迪"), ("002714", "牧原股份"),
    ("300014", "亿纬锂能"), ("300015", "爱尔眼科"), ("300059", "东方财富"),
    ("300122", "智飞生物"), ("300124", "汇川技术"), ("300274", "阳光电源"),
    ("300750", "宁德时代"), ("600000", "浦发银行"), ("600009", "上海机场"),
    ("600019", "宝钢股份"), ("600028", "中国石化"), ("600030", "中信证券"),
    ("600036", "招商银行"), ("600048", "保利发展"), ("600050", "中国联通"),
    ("600104", "上汽集团"), ("600276", "恒瑞医药"), ("600309", "万华化学"),
    ("600519", "贵州茅台"), ("600585", "海螺水泥"), ("600588", "用友网络"),
    ("600690", "海尔智家"), ("600887", "伊利股份"), ("600900", "长江电力"),
    ("601012", "隆基绿能"), ("601088", "中国神华"), ("601166", "兴业银行"),
    ("601318", "中国平安"), ("601398", "工商银行"), ("601601", "中国太保"),
    ("601628", "中国人寿"), ("601668", "中国建筑"), ("601888", "中国中免"),
    ("603259", "药明康德"), ("688981", "中芯国际"),
]


def generate_mock_stock_list() -> pd.DataFrame:
    """Generate representative A-share stock list."""
    return pd.DataFrame(MOCK_STOCKS, columns=["code", "name"])


def _code_to_seed(code: str) -> int:
    """Deterministic seed from stock code."""
    return int(hashlib.md5(code.encode()).hexdigest()[:8], 16)


def _get_trading_days(start_date: str, end_date: str) -> list:
    """Generate trading days (skip weekends, approximate holidays)."""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Skip weekends
            days.append(current)
        current += timedelta(days=1)
    return days


def generate_mock_kline(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Generate realistic daily K-line data for a stock.

    Uses a geometric random walk with mean-reverting volatility.
    """
    seed = _code_to_seed(symbol)
    rng = np.random.RandomState(seed)

    trading_days = _get_trading_days(start_date, end_date)
    if not trading_days:
        return pd.DataFrame()

    n_days = len(trading_days)

    # Starting price based on stock code (range 5-500)
    base_price = 5 + (seed % 495)
    if symbol.startswith("6005"):  # Blue chips tend to be higher
        base_price = max(base_price, 50)
    if symbol.startswith("300"):  # GEM stocks
        base_price = 10 + (seed % 200)

    # Generate daily returns with slight positive drift
    daily_returns = rng.normal(0.0002, 0.022, n_days)
    # Add occasional larger moves
    big_moves = rng.choice(n_days, size=n_days // 20, replace=False)
    daily_returns[big_moves] *= rng.uniform(2, 4, len(big_moves))

    # Build close prices
    close_prices = base_price * np.cumprod(1 + daily_returns)
    close_prices = np.maximum(close_prices, 1.0)  # Floor at 1 yuan

    # Generate OHLC from close
    daily_range = np.abs(rng.normal(0.02, 0.01, n_days))
    high_prices = close_prices * (1 + daily_range * rng.uniform(0.3, 1.0, n_days))
    low_prices = close_prices * (1 - daily_range * rng.uniform(0.3, 1.0, n_days))
    open_prices = low_prices + (high_prices - low_prices) * rng.uniform(0.2, 0.8, n_days)

    # Ensure OHLC consistency
    high_prices = np.maximum(high_prices, np.maximum(open_prices, close_prices))
    low_prices = np.minimum(low_prices, np.minimum(open_prices, close_prices))

    # Volume: base volume with correlation to price movement
    base_volume = (seed % 50000 + 10000) * 100
    vol_noise = rng.lognormal(0, 0.5, n_days)
    abs_returns = np.abs(daily_returns)
    vol_factor = 1 + abs_returns * 20  # Higher volume on big moves
    volume = (base_volume * vol_noise * vol_factor).astype(int)

    # Amount (approximate)
    amount = volume * close_prices

    # Turnover rate
    turnover = rng.uniform(0.5, 8.0, n_days)

    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in trading_days],
        "code": symbol,
        "open": np.round(open_prices, 2),
        "close": np.round(close_prices, 2),
        "high": np.round(high_prices, 2),
        "low": np.round(low_prices, 2),
        "volume": volume,
        "amount": np.round(amount, 2),
        "amplitude": np.round((high_prices - low_prices) / np.roll(close_prices, 1) * 100, 2),
        "pct_change": np.round(daily_returns * 100, 2),
        "change": np.round(np.diff(close_prices, prepend=close_prices[0]), 2),
        "turnover": np.round(turnover, 2),
    })

    return df
