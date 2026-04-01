"""Safe Python expression evaluator for stock screening."""

import ast
import pandas as pd
import numpy as np
import logging

import indicators as ind

logger = logging.getLogger(__name__)

# Whitelist of allowed names in formula context
ALLOWED_BUILTINS = {"True", "False", "None", "abs", "max", "min", "int", "float", "bool", "len"}

# Disallowed AST node types for security
DISALLOWED_NODES = (
    ast.Import, ast.ImportFrom, ast.Delete,
    ast.ClassDef, ast.AsyncFunctionDef, ast.FunctionDef,
    ast.Global, ast.Nonlocal, ast.Exec if hasattr(ast, "Exec") else ast.Pass,
    ast.Yield, ast.YieldFrom,
)


def _validate_ast(node) -> list:
    """Walk AST and return list of security violations."""
    violations = []
    for child in ast.walk(node):
        if isinstance(child, DISALLOWED_NODES):
            violations.append(f"Disallowed construct: {type(child).__name__}")
        if isinstance(child, ast.Attribute):
            if str(getattr(child, "attr", "")).startswith("__"):
                violations.append(f"Dunder access not allowed: {child.attr}")
        if isinstance(child, ast.Name):
            if str(child.id).startswith("__"):
                violations.append(f"Dunder name not allowed: {child.id}")
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                if child.func.id in ("eval", "exec", "compile", "open",
                                      "__import__", "getattr", "setattr",
                                      "delattr", "globals", "locals"):
                    violations.append(f"Disallowed function: {child.func.id}")
    return violations


class PythonEngine:
    """Evaluates Python/pandas expressions safely."""

    def validate(self, formula: str) -> tuple:
        """Validate formula syntax and security."""
        # Handle multi-line formulas (convert to exec-style)
        lines = formula.strip().split("\n")
        if len(lines) > 1:
            # Multi-line: validate each line
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    ast.parse(line)
                except SyntaxError as e:
                    return False, f"Syntax error on line {i+1}: {e.msg}"
        else:
            try:
                tree = ast.parse(formula, mode="eval")
            except SyntaxError:
                try:
                    tree = ast.parse(formula, mode="exec")
                except SyntaxError as e:
                    return False, f"Syntax error: {e.msg}"

        # Security check
        tree = ast.parse(formula)
        violations = _validate_ast(tree)
        if violations:
            return False, f"Security violation: {'; '.join(violations)}"

        return True, "Formula is valid"

    def evaluate(self, formula: str, df: pd.DataFrame, target_idx: int) -> bool:
        """Evaluate Python expression on stock data.

        Provides lowercase price variables and indicator functions.
        """
        # Build namespace
        namespace = {
            # Price data
            "close": df["close"].astype(float),
            "open": df["open"].astype(float),
            "high": df["high"].astype(float),
            "low": df["low"].astype(float),
            "vol": df["volume"].astype(float),
            "volume": df["volume"].astype(float),
            "amount": df["amount"].astype(float),
            # Also uppercase
            "CLOSE": df["close"].astype(float),
            "OPEN": df["open"].astype(float),
            "HIGH": df["high"].astype(float),
            "LOW": df["low"].astype(float),
            "VOL": df["volume"].astype(float),
            "AMOUNT": df["amount"].astype(float),
            # Indicator functions (lowercase)
            "ma": ind.MA,
            "ema": ind.EMA,
            "sma": ind.SMA,
            "ref": ind.REF,
            "cross": ind.CROSS,
            "longcross": ind.LONGCROSS,
            "hhv": ind.HHV,
            "llv": ind.LLV,
            "count": ind.COUNT,
            "barslast": ind.BARSLAST,
            "every": ind.EVERY,
            "exist": ind.EXIST,
            "sum_n": ind.SUM_N,
            "abs_s": ind.ABS_S,
            "max_s": ind.MAX_S,
            "min_s": ind.MIN_S,
            "sqrt_s": ind.SQRT_S,
            "if_s": ind.IF_S,
            "std": ind.STD,
            "avedev": ind.AVEDEV,
            "macd": ind.MACD,
            "kdj": ind.KDJ,
            "rsi": ind.RSI,
            "boll": ind.BOLL,
            "wr": ind.WR,
            "atr": ind.ATR,
            # Also uppercase
            "MA": ind.MA,
            "EMA": ind.EMA,
            "SMA": ind.SMA,
            "REF": ind.REF,
            "CROSS": ind.CROSS,
            "HHV": ind.HHV,
            "LLV": ind.LLV,
            "MACD": ind.MACD,
            "KDJ": ind.KDJ,
            "RSI": ind.RSI,
            "BOLL": ind.BOLL,
            # Modules
            "np": np,
            "pd": pd,
            # Safe builtins
            "True": True,
            "False": False,
            "None": None,
            "abs": abs,
            "max": max,
            "min": min,
            "int": int,
            "float": float,
            "bool": bool,
        }

        safe_builtins = {
            "__builtins__": {
                "True": True, "False": False, "None": None,
                "abs": abs, "max": max, "min": min,
                "int": int, "float": float, "bool": bool,
                "len": len, "range": range, "round": round,
            }
        }

        try:
            lines = formula.strip().split("\n")
            result = None
            if len(lines) > 1:
                # Multi-line: exec all but last, eval last
                for line in lines[:-1]:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    exec(line, safe_builtins, namespace)
                last_line = lines[-1].strip()
                if "=" in last_line and not any(
                    op in last_line for op in ["==", "!=", ">=", "<="]
                ):
                    exec(last_line, safe_builtins, namespace)
                    # Try to find the result variable
                    var_name = last_line.split("=")[0].strip()
                    result = namespace.get(var_name)
                else:
                    result = eval(last_line, safe_builtins, namespace)
            else:
                try:
                    result = eval(formula, safe_builtins, namespace)
                except SyntaxError:
                    exec(formula, safe_builtins, namespace)
                    return False

            # Extract boolean at target index
            if result is None:
                return False
            if isinstance(result, pd.Series):
                if target_idx < len(result):
                    val = result.iloc[target_idx]
                    return bool(val) if not pd.isna(val) else False
                return False
            if isinstance(result, tuple):
                first = result[0]
                if isinstance(first, pd.Series) and target_idx < len(first):
                    val = first.iloc[target_idx]
                    return bool(val) if not pd.isna(val) else False
                return False
            return bool(result)

        except Exception as e:
            logger.warning(f"Python eval error: {e}")
            return False
