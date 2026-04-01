"""Data layer: AKShare fetching, caching, normalization, mock fallback.

K-line data sources (in priority order):
  1. Tencent (stock_zh_a_hist_tx) — gu.qq.com, more stable
  2. East Money (stock_zh_a_hist) — push2his.eastmoney.com, richer columns
"""

import pandas as pd
import os
import time
import logging
import json
import threading
from datetime import datetime, timedelta
from contextlib import contextmanager

from mock_data import generate_mock_stock_list, generate_mock_kline

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")

DATA_MODE = "auto"
DATA_START_DATE = "20210101"

_stocklist_api_available = None
_kline_source = None  # "tencent", "eastmoney", or None
_stock_list_cache = None

_update_running = False
_update_progress = {
    "status": "idle", "current": 0, "total": 0,
    "code": "", "name": "", "message": "",
    "log": [], "success_count": 0, "error_count": 0,
}


# ─── Proxy Bypass ────────────────────────────────────────────────────

_PROXY_ENV_KEYS = [
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy",
]

# placeholder — filled inside _bypass_proxy
_orig_get = _orig_post = None


@contextmanager
def _bypass_proxy():
    """Temporarily remove proxy env vars and patch requests."""
    saved = {}
    for key in _PROXY_ENV_KEYS:
        if key in os.environ:
            saved[key] = os.environ.pop(key)
    try:
        try:
            import requests
            orig_get = requests.Session.get
            orig_post = requests.Session.post

            def _patched_get(self, url, **kwargs):
                kwargs.setdefault("proxies", {"http": None, "https": None})
                return orig_get(self, url, **kwargs)

            def _patched_post(self, url, **kwargs):
                kwargs.setdefault("proxies", {"http": None, "https": None})
                return orig_post(self, url, **kwargs)

            requests.Session.get = _patched_get
            requests.Session.post = _patched_post
        except ImportError:
            orig_get = orig_post = None

        yield
    finally:
        for key, val in saved.items():
            os.environ[key] = val
        try:
            import requests
            if orig_get:
                requests.Session.get = orig_get
            if orig_post:
                requests.Session.post = orig_post
        except ImportError:
            pass


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


# ─── Symbol Conversion ──────────────────────────────────────────────

def _code_to_tx(code: str) -> str:
    """Convert bare code '000001' to Tencent format 'sz000001'."""
    if code.startswith(("sh", "sz")):
        return code
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


# ─── Data Source Detection ───────────────────────────────────────────

def _check_stocklist_api(force: bool = False) -> bool:
    global _stocklist_api_available
    if not force and _stocklist_api_available is not None:
        return _stocklist_api_available
    try:
        import akshare as ak
        with _bypass_proxy():
            df = ak.stock_info_a_code_name()
            if df is not None and len(df) >= 100:
                _stocklist_api_available = True
                logger.info(f"Stock list OK: {len(df)} stocks")
            else:
                _stocklist_api_available = False
    except Exception as e:
        logger.warning(f"Stock list API unavailable: {e}")
        _stocklist_api_available = False
    return _stocklist_api_available


def _detect_kline_source(force: bool = False):
    """Detect which K-line source works.  Returns 'tencent', 'eastmoney', or None."""
    global _kline_source
    if not force and _kline_source is not None:
        return _kline_source

    import akshare as ak

    # Try Tencent first (more stable)
    try:
        with _bypass_proxy():
            df = ak.stock_zh_a_hist_tx(
                symbol="sz000001", start_date="20240101",
                end_date="20240110", adjust="qfq",
            )
        if df is not None and len(df) > 0:
            _kline_source = "tencent"
            logger.info("K-line source: Tencent (腾讯)")
            return _kline_source
    except Exception as e:
        logger.debug(f"Tencent K-line test failed: {e}")

    # Try East Money
    try:
        with _bypass_proxy():
            df = ak.stock_zh_a_hist(
                symbol="000001", period="daily",
                start_date="20240101", end_date="20240110",
                adjust="qfq",
            )
        if df is not None and len(df) > 0:
            _kline_source = "eastmoney"
            logger.info("K-line source: East Money (东方财富)")
            return _kline_source
    except Exception as e:
        logger.debug(f"East Money K-line test failed: {e}")

    _kline_source = None
    logger.warning("No K-line data source available")
    return None


# ─── K-line Fetch (with retry + dual source) ────────────────────────

def _fetch_kline_raw(symbol: str, start_date: str, end_date: str,
                     adjust: str = "qfq", source: str = "tencent") -> pd.DataFrame:
    """Fetch raw K-line from a specific source."""
    import akshare as ak
    with _bypass_proxy():
        if source == "tencent":
            tx_sym = _code_to_tx(symbol)
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_sym, start_date=start_date,
                end_date=end_date, adjust=adjust,
            )
        else:
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date,
                adjust=adjust,
            )
    return df


def _fetch_kline_with_retry(symbol, start_date, end_date, adjust="qfq",
                            max_retries=3, base_delay=1.5):
    """Fetch K-line with retry.  Uses detected source, falls back to alt."""
    source = _kline_source or "tencent"
    alt_source = "eastmoney" if source == "tencent" else "tencent"

    last_err = None
    for attempt in range(max_retries):
        try:
            return _fetch_kline_raw(symbol, start_date, end_date, adjust, source)
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.debug(f"Retry {attempt+1}/{max_retries} {symbol} ({source}) in {delay}s")
                time.sleep(delay)

    # Primary exhausted — one shot with alt source
    try:
        logger.debug(f"Trying alt source {alt_source} for {symbol}")
        return _fetch_kline_raw(symbol, start_date, end_date, adjust, alt_source)
    except Exception:
        pass

    raise last_err


# ─── Column Normalization ────────────────────────────────────────────

# East Money returns Chinese column names
_EM_COLUMN_MAP = {
    "日期": "date", "股票代码": "code",
    "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount",
    "振幅": "amplitude", "涨跌幅": "pct_change",
    "涨跌额": "change", "换手率": "turnover",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns from any source to standard English names.

    Standard columns: date, open, close, high, low, volume
    Optional columns: amount, pct_change, turnover, amplitude, change
    """
    # East Money (Chinese columns)
    if "日期" in df.columns:
        df = df.rename(columns=_EM_COLUMN_MAP)
        return df

    # Tencent: already English, but 'amount' is actually volume
    if "amount" in df.columns and "volume" not in df.columns:
        df = df.rename(columns={"amount": "volume"})

    # Compute pct_change if missing
    if "pct_change" not in df.columns and "close" in df.columns:
        close = df["close"].astype(float)
        df["pct_change"] = close.pct_change() * 100
        df["pct_change"] = df["pct_change"].round(2)

    return df


# ─── Stock List ──────────────────────────────────────────────────────

def get_stock_list() -> pd.DataFrame:
    """Returns DataFrame with columns: code, name."""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache

    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, "stock_list.pkl")

    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 86400:
            _stock_list_cache = pd.read_pickle(cache_path)
            logger.info(f"Loaded {len(_stock_list_cache)} stocks from cache")
            return _stock_list_cache

    if DATA_MODE != "mock" and _check_stocklist_api():
        try:
            import akshare as ak
            with _bypass_proxy():
                df = ak.stock_info_a_code_name()
            if list(df.columns) != ["code", "name"]:
                df.columns = ["code", "name"]
            df.to_pickle(cache_path)
            _stock_list_cache = df
            logger.info(f"Loaded {len(df)} stocks from AKShare")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch stock list: {e}")

    # Expired cache fallback
    if os.path.exists(cache_path):
        try:
            _stock_list_cache = pd.read_pickle(cache_path)
            logger.info(f"Loaded {len(_stock_list_cache)} stocks from expired cache")
            return _stock_list_cache
        except Exception:
            pass

    df = generate_mock_stock_list()
    df.to_pickle(cache_path)
    _stock_list_cache = df
    logger.info(f"Using mock stock list: {len(df)} stocks")
    return df


# ─── Historical K-line Data ─────────────────────────────────────────

def get_stock_hist(symbol: str, start_date: str, end_date: str,
                   adjust: str = "qfq") -> pd.DataFrame:
    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"hist_{symbol}_{adjust}.pkl")

    if os.path.exists(cache_path):
        df = pd.read_pickle(cache_path)
        filtered = _filter_range(df, start_date, end_date)
        if not filtered.empty:
            return filtered

    if DATA_MODE == "mock":
        df = generate_mock_kline(symbol, start_date, end_date)
        if not df.empty:
            df.to_pickle(cache_path)
        return df

    if _detect_kline_source():
        try:
            df = _fetch_kline_with_retry(symbol, start_date, end_date, adjust)
            if df is not None and not df.empty:
                df = _normalize_columns(df)
                if os.path.exists(cache_path):
                    existing = pd.read_pickle(cache_path)
                    df = pd.concat([existing, df]).drop_duplicates(
                        subset=["date"]).sort_values("date").reset_index(drop=True)
                df.to_pickle(cache_path)
                return _filter_range(df, start_date, end_date)
        except Exception as e:
            logger.warning(f"K-line fetch failed for {symbol}: {e}")

    if os.path.exists(cache_path):
        df = pd.read_pickle(cache_path)
        filtered = _filter_range(df, start_date, end_date)
        if not filtered.empty:
            return filtered

    if _kline_source is None:
        df = generate_mock_kline(symbol, start_date, end_date)
        if not df.empty:
            df.to_pickle(cache_path)
        return df

    return pd.DataFrame()


def _filter_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if df.empty:
        return df
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)
    dates = df["date"].astype(str)
    return df[(dates >= start) & (dates <= end)].reset_index(drop=True)


def _normalize_date(date_str: str) -> str:
    if len(date_str) == 8 and "-" not in date_str:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str


# ─── Screening helpers ───────────────────────────────────────────────

def get_screening_data(symbol, screen_date, lookback_days=400, forward_days=40):
    screen_dt = datetime.strptime(screen_date.replace("-", ""), "%Y%m%d")
    start_dt = screen_dt - timedelta(days=lookback_days)
    end_dt = screen_dt + timedelta(days=forward_days)
    return get_stock_hist(symbol, start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d"))


def find_date_index(df, target_date):
    if df.empty:
        return -1
    target = _normalize_date(target_date)
    dates = df["date"].astype(str)
    matches = df.index[dates == target].tolist()
    if matches:
        return matches[0]
    prior = df[dates <= target]
    return prior.index[-1] if not prior.empty else -1


# ─── Data Status & Batch Update ──────────────────────────────────────

STATUS_FILE = os.path.join(CACHE_DIR, "update_status.json")


def get_data_status():
    _ensure_cache_dir()
    stocks = get_stock_list()
    total_stocks = len(stocks)

    cached_count = 0
    latest_date = None
    oldest_date = None
    for _, row in stocks.iterrows():
        cp = os.path.join(CACHE_DIR, f"hist_{row['code']}_qfq.pkl")
        if os.path.exists(cp):
            cached_count += 1
            try:
                df = pd.read_pickle(cp)
                if not df.empty:
                    last = str(df["date"].iloc[-1])
                    first = str(df["date"].iloc[0])
                    if latest_date is None or last > latest_date:
                        latest_date = last
                    if oldest_date is None or first < oldest_date:
                        oldest_date = first
            except Exception:
                pass

    last_update = None
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                last_update = json.load(f).get("last_update")
        except Exception:
            pass

    return {
        "total_stocks": total_stocks,
        "cached_stocks": cached_count,
        "data_start": oldest_date,
        "data_end": latest_date,
        "last_update": last_update,
        "is_updating": _update_running,
        "data_mode": DATA_MODE,
        "akshare_available": bool(_kline_source),
        "kline_source": _kline_source,
    }


def _save_update_status():
    _ensure_cache_dir()
    with open(STATUS_FILE, "w") as f:
        json.dump({"last_update": datetime.now().isoformat(timespec="seconds")}, f)


def get_update_progress():
    return dict(_update_progress)


def start_batch_update():
    global _update_running
    if _update_running:
        return {"success": False, "message": "Update already in progress"}
    t = threading.Thread(target=_run_batch_update, daemon=True)
    t.start()
    return {"success": True, "message": "Update started"}


def _run_batch_update():
    global _update_running, _update_progress, _stock_list_cache

    _update_running = True
    _update_progress = {
        "status": "running", "current": 0, "total": 0,
        "code": "", "name": "", "message": "检测数据源...",
        "log": [], "success_count": 0, "error_count": 0,
    }

    try:
        # 1. Stock list
        _stock_list_cache = None
        _update_progress["message"] = "获取股票列表..."
        _check_stocklist_api(force=True)

        # 2. Detect K-line source (Tencent → East Money)
        _update_progress["message"] = "测试K线数据源..."
        source = _detect_kline_source(force=True)

        if source is None:
            _update_progress.update({
                "status": "error",
                "message": "所有K线数据源均不可用，请检查网络或关闭代理后重试",
            })
            _update_progress["log"].append("错误: 腾讯和东方财富K线接口均无法访问")
            _update_progress["log"].append("提示: 请关闭系统代理 (ClashX/Surge/V2Ray) 后重试")
            return

        source_label = "腾讯" if source == "tencent" else "东方财富"
        stocks = get_stock_list()
        total = len(stocks)
        today_str = datetime.now().strftime("%Y%m%d")
        start_str = DATA_START_DATE

        _update_progress["total"] = total
        _update_progress["message"] = f"开始更新: {total} 只股票 (数据源: {source_label})"
        _update_progress["log"].append(
            f"数据源: {source_label}, 范围: {start_str}-{today_str}, 共 {total} 只"
        )

        success_count = 0
        error_count = 0
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 15

        for i, (_, row) in enumerate(stocks.iterrows()):
            code = row["code"]
            name = row["name"]
            cache_path = os.path.join(CACHE_DIR, f"hist_{code}_qfq.pkl")

            _update_progress.update({"current": i + 1, "code": code, "name": name})

            try:
                existing_end = None
                if os.path.exists(cache_path):
                    try:
                        existing = pd.read_pickle(cache_path)
                        if not existing.empty:
                            existing_end = str(existing["date"].iloc[-1]).replace("-", "")
                    except Exception:
                        pass

                fetch_start = existing_end if existing_end and existing_end >= start_str else start_str

                if existing_end and existing_end >= today_str:
                    success_count += 1
                    consecutive_errors = 0
                    _update_progress.update({
                        "message": f"{code} {name} — 已是最新",
                        "success_count": success_count, "error_count": error_count,
                    })
                    continue

                df = _fetch_kline_with_retry(
                    code, fetch_start, today_str, "qfq",
                    max_retries=3, base_delay=1.5,
                )

                if df is not None and not df.empty:
                    df = _normalize_columns(df)
                    if os.path.exists(cache_path):
                        try:
                            old = pd.read_pickle(cache_path)
                            df = pd.concat([old, df]).drop_duplicates(
                                subset=["date"]).sort_values("date").reset_index(drop=True)
                        except Exception:
                            pass
                    df.to_pickle(cache_path)
                    rows = len(df)
                else:
                    rows = 0

                success_count += 1
                consecutive_errors = 0
                msg = f"{code} {name} — {rows} 条"
                _update_progress.update({
                    "message": msg, "success_count": success_count, "error_count": error_count,
                })
                _update_progress["log"].append(msg)

                time.sleep(0.5)

            except Exception as e:
                error_count += 1
                consecutive_errors += 1
                err_short = str(e)[:60]
                msg = f"{code} {name} — 失败: {err_short}"
                _update_progress.update({
                    "message": msg, "success_count": success_count, "error_count": error_count,
                })
                _update_progress["log"].append(msg)
                time.sleep(1.0)

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    abort_msg = (f"连续 {MAX_CONSECUTIVE_ERRORS} 只失败，"
                                 f"已停止 (成功 {success_count}, 失败 {error_count})")
                    _update_progress["log"].append(abort_msg)
                    _update_progress.update({
                        "status": "error",
                        "message": abort_msg,
                        "success_count": success_count,
                        "error_count": error_count,
                    })
                    _save_update_status()
                    return

        _save_update_status()
        _update_progress.update({
            "status": "completed",
            "message": f"更新完成: {success_count} 成功, {error_count} 失败",
            "success_count": success_count,
            "error_count": error_count,
        })

    except Exception as e:
        _update_progress.update({
            "status": "error",
            "message": f"更新失败: {str(e)}",
        })
    finally:
        _update_running = False
