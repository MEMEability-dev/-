"""Pydantic request/response models for the stock screening API."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum


class FormulaType(str, Enum):
    TDX = "tdx"
    PYTHON = "python"
    PSEUDO = "pseudo"


class ScreenRequest(BaseModel):
    formula: str
    formula_type: FormulaType
    date: str  # YYYYMMDD
    exclude_st: bool = True
    market_filter: Optional[str] = None  # 主板 / 创业板 / 科创板 / None


class StockResult(BaseModel):
    code: str
    name: str
    date_price: float
    return_3d: Optional[float] = None
    return_5d: Optional[float] = None
    return_10d: Optional[float] = None
    return_20d: Optional[float] = None


class ScreenResponse(BaseModel):
    success: bool
    message: str = ""
    total_screened: int = 0
    total_matched: int = 0
    results: List[StockResult] = []
    stats: Dict = {}


class ValidateRequest(BaseModel):
    formula: str
    formula_type: FormulaType


class ValidateResponse(BaseModel):
    valid: bool
    message: str = ""
    normalized: str = ""


# ─── Strategy Persistence ────────────────────────────────────────────

class Strategy(BaseModel):
    id: str = ""                          # Auto-generated UUID
    name: str                             # User-given name
    description: str = ""                 # Optional description
    formula: str                          # Formula text
    formula_type: FormulaType             # tdx / python / pseudo
    exclude_st: bool = True
    market_filter: Optional[str] = None
    created_at: str = ""                  # ISO timestamp
    updated_at: str = ""


class StrategySaveRequest(BaseModel):
    id: Optional[str] = None              # None = create new, string = update existing
    name: str
    description: str = ""
    formula: str
    formula_type: FormulaType
    exclude_st: bool = True
    market_filter: Optional[str] = None
