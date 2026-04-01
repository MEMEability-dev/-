"""FastAPI application - A-Share Stock Screening Platform."""

import sys
import os
import logging
import json
import uuid
import threading
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from models import (
    FormulaType, ScreenRequest, ScreenResponse, StockResult,
    ValidateRequest, ValidateResponse,
    Strategy, StrategySaveRequest,
)
from data_layer import (
    get_stock_list, get_screening_data, find_date_index,
    get_data_status, start_batch_update, get_update_progress,
)
from tdx_engine import TDXEngine
from python_engine import PythonEngine
from pseudo_engine import PseudoEngine
from formula_library import FORMULA_TEMPLATES
from performance import calculate_returns, aggregate_stats
from indicators import MA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Initialize App & Engines ────────────────────────────────────────

app = FastAPI(title="A-Share Stock Screener", version="1.2.0")

tdx_engine = TDXEngine()
python_engine = PythonEngine()
pseudo_engine = PseudoEngine()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# ─── Screening Progress State ──────────────────────────────────────

_screen_running = False
_screen_progress = {
    "status": "idle",  # idle, running, completed, error
    "current": 0,
    "total": 0,
    "matched": 0,
    "code": "",
    "name": "",
    "message": "",
}
_screen_result = None  # Stores final ScreenResponse when completed


def _get_engine(formula_type: FormulaType):
    if formula_type == FormulaType.TDX:
        return tdx_engine
    elif formula_type == FormulaType.PYTHON:
        return python_engine
    elif formula_type == FormulaType.PSEUDO:
        return pseudo_engine
    raise ValueError(f"Unknown formula type: {formula_type}")


def _filter_by_market(stocks, market: str):
    """Filter stocks by market segment based on code prefix."""
    if market == "主板":
        return stocks[
            stocks["code"].str.startswith("60") | stocks["code"].str.startswith("000")
        ]
    elif market == "创业板":
        return stocks[stocks["code"].str.startswith("300")]
    elif market == "科创板":
        return stocks[stocks["code"].str.startswith("688")]
    return stocks


# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/")
@app.head("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/stock_list")
async def api_stock_list():
    df = get_stock_list()
    return {"stocks": df.to_dict(orient="records"), "total": len(df)}


@app.post("/api/formula/validate")
async def api_validate(req: ValidateRequest):
    engine = _get_engine(req.formula_type)
    valid, msg = engine.validate(req.formula)
    return ValidateResponse(valid=valid, message=msg)


@app.post("/api/screen")
async def api_screen(req: ScreenRequest):
    """Start screening in background. Poll /api/screen/progress for status."""
    global _screen_running, _screen_progress, _screen_result

    if _screen_running:
        return {"success": False, "message": "选股正在进行中，请稍候"}

    # Validate formula first (fast, synchronous)
    engine = _get_engine(req.formula_type)
    valid, msg = engine.validate(req.formula)
    if not valid:
        return ScreenResponse(success=False, message=f"公式错误: {msg}")

    # Reset state
    _screen_result = None
    _screen_progress = {
        "status": "running", "current": 0, "total": 0,
        "matched": 0, "code": "", "name": "", "message": "正在准备股票列表...",
    }

    # Launch background thread
    t = threading.Thread(
        target=_run_screening,
        args=(req.formula, req.formula_type, req.date, req.exclude_st, req.market_filter),
        daemon=True,
    )
    t.start()
    return {"success": True, "message": "选股已开始", "async": True}


@app.get("/api/screen/progress")
async def api_screen_progress():
    """Poll screening progress."""
    result = dict(_screen_progress)
    if _screen_progress["status"] == "completed" and _screen_result is not None:
        result["data"] = _screen_result
    return result


def _run_screening(formula: str, formula_type: FormulaType, date: str,
                   exclude_st: bool, market_filter):
    """Background worker for stock screening."""
    global _screen_running, _screen_progress, _screen_result

    _screen_running = True
    try:
        # 1. Get stock list
        stocks = get_stock_list()

        # 2. Apply filters
        if exclude_st:
            stocks = stocks[~stocks["name"].str.contains("ST", na=False)]
        if market_filter:
            stocks = _filter_by_market(stocks, market_filter)

        total = len(stocks)
        _screen_progress["total"] = total
        _screen_progress["message"] = f"扫描 {total} 只股票..."

        # 3. Get engine
        engine = _get_engine(formula_type)

        # 4. Screen each stock
        results = []
        errors = 0
        screened = 0

        for i, (_, stock) in enumerate(stocks.iterrows()):
            code = stock["code"]
            name = stock["name"]

            _screen_progress.update({
                "current": i + 1, "code": code, "name": name,
                "matched": len(results),
                "message": f"扫描 {code} {name}",
            })

            try:
                df = get_screening_data(code, date, lookback_days=400, forward_days=40)
                if df.empty or len(df) < 30:
                    continue

                target_idx = find_date_index(df, date)
                if target_idx < 0:
                    continue

                screened += 1
                matched = engine.evaluate(formula, df, target_idx)

                if matched:
                    returns = calculate_returns(df, target_idx)
                    results.append(StockResult(
                        code=code,
                        name=name,
                        date_price=round(float(df.iloc[target_idx]["close"]), 2),
                        return_3d=returns.get("return_3d"),
                        return_5d=returns.get("return_5d"),
                        return_10d=returns.get("return_10d"),
                        return_20d=returns.get("return_20d"),
                    ))

            except Exception as e:
                errors += 1
                logger.debug(f"Error screening {code}: {e}")

        # 5. Aggregate stats
        stats = aggregate_stats([r.model_dump() for r in results])

        _screen_result = ScreenResponse(
            success=True,
            message=f"扫描 {screened} 只股票, {errors} 个错误",
            total_screened=screened,
            total_matched=len(results),
            results=results,
            stats=stats,
        ).model_dump()

        _screen_progress.update({
            "status": "completed",
            "matched": len(results),
            "message": f"完成: 匹配 {len(results)} 只 / 扫描 {screened} 只",
        })

    except Exception as e:
        logger.error(f"Screening error: {e}")
        _screen_progress.update({
            "status": "error",
            "message": f"选股失败: {str(e)}",
        })
    finally:
        _screen_running = False


@app.get("/api/kline/{stock_code}")
async def api_kline(stock_code: str, center_date: str = "",
                    days_before: int = 60, days_after: int = 30):
    """Return K-line data for charting."""
    if not center_date:
        raise HTTPException(400, "center_date is required")

    df = get_screening_data(
        stock_code, center_date,
        lookback_days=days_before + 100,  # Extra for MA calculation
        forward_days=days_after,
    )

    if df.empty:
        raise HTTPException(404, f"No data for {stock_code}")

    # Calculate MA overlays
    close_series = df["close"].astype(float)
    df["ma5"] = MA(close_series, 5)
    df["ma10"] = MA(close_series, 10)
    df["ma20"] = MA(close_series, 20)

    # Find screen date for marking
    screen_date_normalized = center_date
    if len(center_date) == 8:
        screen_date_normalized = f"{center_date[:4]}-{center_date[4:6]}-{center_date[6:8]}"

    def _safe_list(series):
        """Convert Series to list, replacing NaN with None for JSON."""
        return [None if pd.isna(v) else round(float(v), 2) for v in series]

    return {
        "code": stock_code,
        "dates": df["date"].astype(str).tolist(),
        "open": _safe_list(df["open"]),
        "close": _safe_list(df["close"]),
        "high": _safe_list(df["high"]),
        "low": _safe_list(df["low"]),
        "volume": [int(v) if not pd.isna(v) else 0 for v in df["volume"]],
        "amount": _safe_list(df["amount"]) if "amount" in df.columns else [],
        "pct_change": _safe_list(df["pct_change"]) if "pct_change" in df.columns else [],
        "ma5": _safe_list(df["ma5"]),
        "ma10": _safe_list(df["ma10"]),
        "ma20": _safe_list(df["ma20"]),
        "screen_date": screen_date_normalized,
    }


@app.get("/api/formula/templates")
async def api_templates():
    return FORMULA_TEMPLATES


# ─── Data Update ─────────────────────────────────────────────────────

@app.get("/api/data/status")
async def api_data_status():
    """Get current data cache status."""
    return get_data_status()


@app.post("/api/data/update")
async def api_data_update():
    """Start batch data update in background. Poll /api/data/progress for status."""
    result = start_batch_update()
    return result


@app.get("/api/data/progress")
async def api_data_progress():
    """Get current data update progress (for polling)."""
    return get_update_progress()


# ─── Strategy Persistence ────────────────────────────────────────────

STRATEGIES_FILE = os.path.join(os.path.dirname(__file__), "data_cache", "strategies.json")


def _load_strategies():
    """Load strategies from JSON file."""
    if os.path.exists(STRATEGIES_FILE):
        try:
            with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_strategies(strategies):
    """Persist strategies to JSON file."""
    os.makedirs(os.path.dirname(STRATEGIES_FILE), exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


@app.get("/api/strategies")
async def api_list_strategies():
    """List all saved strategies."""
    strategies = _load_strategies()
    return {"strategies": strategies, "total": len(strategies)}


@app.post("/api/strategies")
async def api_save_strategy(req: StrategySaveRequest):
    """Create or update a strategy."""
    strategies = _load_strategies()
    now = datetime.now().isoformat(timespec="seconds")

    if req.id:
        # Update existing
        found = False
        for s in strategies:
            if s["id"] == req.id:
                s["name"] = req.name
                s["description"] = req.description
                s["formula"] = req.formula
                s["formula_type"] = req.formula_type.value
                s["exclude_st"] = req.exclude_st
                s["market_filter"] = req.market_filter
                s["updated_at"] = now
                found = True
                break
        if not found:
            raise HTTPException(404, f"Strategy {req.id} not found")
    else:
        # Create new
        strategy = {
            "id": uuid.uuid4().hex[:12],
            "name": req.name,
            "description": req.description,
            "formula": req.formula,
            "formula_type": req.formula_type.value,
            "exclude_st": req.exclude_st,
            "market_filter": req.market_filter,
            "created_at": now,
            "updated_at": now,
        }
        strategies.append(strategy)

    _save_strategies(strategies)
    return {"success": True, "strategies": strategies}


@app.delete("/api/strategies/{strategy_id}")
async def api_delete_strategy(strategy_id: str):
    """Delete a strategy by ID."""
    strategies = _load_strategies()
    original_len = len(strategies)
    strategies = [s for s in strategies if s["id"] != strategy_id]
    if len(strategies) == original_len:
        raise HTTPException(404, f"Strategy {strategy_id} not found")
    _save_strategies(strategies)
    return {"success": True, "strategies": strategies}


# ─── Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting A-Share Stock Screener on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
