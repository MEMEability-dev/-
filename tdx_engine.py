"""TDX (TongDaXin) formula parser and evaluator using Lark."""

import pandas as pd
import numpy as np
from lark import Lark, Transformer, v_args, Token, Tree
import logging

import indicators as ind

logger = logging.getLogger(__name__)

# ─── Lark Grammar for TDX Formula Language ───────────────────────────

TDX_GRAMMAR = r'''
start: (statement ";"?)+

statement: NAME ":=" expr  -> local_assign
         | NAME ":" expr   -> output_assign
         | expr             -> bare_expr

?expr: or_expr

?or_expr: and_expr (OR_KW and_expr)*

?and_expr: not_expr (AND_KW not_expr)*

?not_expr: NOT_KW compare  -> not_expr
         | compare

?compare: add_expr (COMP_OP add_expr)?

?add_expr: mul_expr (ADD_OP mul_expr)*

?mul_expr: unary (MUL_OP unary)*

?unary: "-" unary          -> neg
      | atom

?atom: func_call
     | NAME               -> var_ref
     | NUMBER             -> number
     | "(" expr ")"

func_call: NAME "(" [expr ("," expr)*] ")" -> func_call

OR_KW: "OR"i | "||"
AND_KW: "AND"i | "&&"
NOT_KW: "NOT"i | "!"
COMP_OP: ">=" | "<=" | "<>" | ">" | "<" | "="

ADD_OP: "+" | "-"
MUL_OP: "*" | "/"

NAME: /[A-Za-z_][A-Za-z0-9_]*/
NUMBER: /[0-9]+(\.[0-9]+)?/

%ignore /[ \t\r\n]+/
%ignore /\{[^}]*\}/
%ignore /\/\/.*/
'''

# ─── Function Registry ───────────────────────────────────────────────

FUNC_REGISTRY = {
    # Moving averages
    "MA": ind.MA,
    "EMA": ind.EMA,
    "SMA": ind.SMA,
    # Reference
    "REF": ind.REF,
    # Cross
    "CROSS": ind.CROSS,
    "LONGCROSS": ind.LONGCROSS,
    # Statistical
    "HHV": ind.HHV,
    "LLV": ind.LLV,
    "COUNT": ind.COUNT,
    "SUM": ind.SUM_N,
    "STD": ind.STD,
    "AVEDEV": ind.AVEDEV,
    # Pattern
    "BARSLAST": ind.BARSLAST,
    "EVERY": ind.EVERY,
    "EXIST": ind.EXIST,
    # Math
    "ABS": ind.ABS_S,
    "MAX": ind.MAX_S,
    "MIN": ind.MIN_S,
    "SQRT": ind.SQRT_S,
    "IF": ind.IF_S,
    "IFF": ind.IF_S,
    "POW": ind.POW_S,
    # Composite (return tuples)
    "MACD": ind.MACD,
    "KDJ": ind.KDJ,
    "RSI": ind.RSI,
    "BOLL": ind.BOLL,
    "WR": ind.WR,
    "ATR": ind.ATR,
    # Aliases
    "NOT": lambda x: ~x.astype(bool) if isinstance(x, pd.Series) else not x,
}

# Built-in price variables
PRICE_VARS = {"CLOSE", "OPEN", "HIGH", "LOW", "VOL", "VOLUME", "AMOUNT", "C", "O", "H", "L", "V"}


# ─── AST Evaluator ──────────────────────────────────────────────────

class TDXEvaluator(Transformer):
    """Evaluate a TDX formula AST against stock data."""

    def __init__(self, context: dict):
        super().__init__()
        self.context = context  # Mutable dict: price data + user vars
        self.last_result = None

    def start(self, items):
        # Return the last evaluated expression
        return self.last_result

    def bare_expr(self, items):
        self.last_result = items[0]
        return items[0]

    def local_assign(self, items):
        name = str(items[0])
        value = items[1]
        self.context[name] = value
        self.last_result = value
        return value

    def output_assign(self, items):
        name = str(items[0])
        value = items[1]
        self.context[name] = value
        self.last_result = value
        return value

    def or_expr(self, items):
        result = items[0]
        i = 1
        while i < len(items):
            if isinstance(items[i], Token) and str(items[i]).upper() in ("OR", "||"):
                i += 1
                right = items[i]
                result = self._logical_or(result, right)
            else:
                right = items[i]
                result = self._logical_or(result, right)
            i += 1
        return result

    def and_expr(self, items):
        result = items[0]
        i = 1
        while i < len(items):
            if isinstance(items[i], Token) and str(items[i]).upper() in ("AND", "&&"):
                i += 1
                right = items[i]
                result = self._logical_and(result, right)
            else:
                right = items[i]
                result = self._logical_and(result, right)
            i += 1
        return result

    def not_expr(self, items):
        val = items[-1]  # Skip the NOT keyword
        if isinstance(val, pd.Series):
            return ~val.astype(bool)
        return not val

    def compare(self, items):
        if len(items) == 1:
            return items[0]
        left, op, right = items[0], str(items[1]), items[2]
        if op == "=":
            return self._compare_op(left, right, "==")
        elif op == "<>":
            return self._compare_op(left, right, "!=")
        elif op == ">=":
            return self._compare_op(left, right, ">=")
        elif op == "<=":
            return self._compare_op(left, right, "<=")
        elif op == ">":
            return self._compare_op(left, right, ">")
        elif op == "<":
            return self._compare_op(left, right, "<")
        return left

    def add_expr(self, items):
        result = items[0]
        i = 1
        while i < len(items):
            op = str(items[i])
            i += 1
            right = items[i]
            if op == "+":
                result = result + right
            elif op == "-":
                result = result - right
            i += 1
        return result

    def mul_expr(self, items):
        result = items[0]
        i = 1
        while i < len(items):
            op = str(items[i])
            i += 1
            right = items[i]
            if op == "*":
                result = result * right
            elif op == "/":
                if isinstance(right, pd.Series):
                    right = right.replace(0, np.nan)
                elif right == 0:
                    right = np.nan
                result = result / right
            i += 1
        return result

    def neg(self, items):
        return -items[0]

    def number(self, items):
        s = str(items[0])
        return float(s) if "." in s else int(s)

    def var_ref(self, items):
        name = str(items[0]).upper()
        # Check user-defined variables first (case-insensitive for TDX)
        if name in self.context:
            return self.context[name]
        # Check with original case
        orig_name = str(items[0])
        if orig_name in self.context:
            return self.context[orig_name]
        raise ValueError(f"Undefined variable: {name}")

    def func_call(self, items):
        func_name = str(items[0]).upper()
        args = items[1:]

        if func_name not in FUNC_REGISTRY:
            raise ValueError(f"Unknown function: {func_name}")

        func = FUNC_REGISTRY[func_name]

        # Special handling for composite indicators that need price data
        if func_name == "MACD" and len(args) == 0:
            args = [self.context["CLOSE"]]
        elif func_name == "KDJ" and len(args) == 0:
            args = [self.context["CLOSE"], self.context["HIGH"], self.context["LOW"]]
        elif func_name == "RSI" and len(args) == 0:
            args = [self.context["CLOSE"]]
        elif func_name == "BOLL" and len(args) == 0:
            args = [self.context["CLOSE"]]
        elif func_name == "WR" and len(args) == 0:
            args = [self.context["CLOSE"], self.context["HIGH"], self.context["LOW"]]
        elif func_name == "ATR" and len(args) == 0:
            args = [self.context["CLOSE"], self.context["HIGH"], self.context["LOW"]]

        try:
            result = func(*args)
            return result
        except Exception as e:
            raise ValueError(f"Error in {func_name}({', '.join(str(a)[:20] for a in args)}): {e}")

    # ─── Helper Methods ──────────────────────────────────────────

    @staticmethod
    def _logical_and(a, b):
        if isinstance(a, pd.Series) and isinstance(b, pd.Series):
            return a.astype(bool) & b.astype(bool)
        if isinstance(a, pd.Series):
            return a.astype(bool) & bool(b)
        if isinstance(b, pd.Series):
            return bool(a) & b.astype(bool)
        return bool(a) and bool(b)

    @staticmethod
    def _logical_or(a, b):
        if isinstance(a, pd.Series) and isinstance(b, pd.Series):
            return a.astype(bool) | b.astype(bool)
        if isinstance(a, pd.Series):
            return a.astype(bool) | bool(b)
        if isinstance(b, pd.Series):
            return bool(a) | b.astype(bool)
        return bool(a) or bool(b)

    @staticmethod
    def _compare_op(left, right, op):
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
        }
        return ops[op](left, right)


# ─── Public API ──────────────────────────────────────────────────────

class TDXEngine:
    def __init__(self):
        self.parser = Lark(TDX_GRAMMAR, parser="earley", ambiguity="resolve")

    def validate(self, formula: str) -> tuple:
        """Parse formula, return (is_valid, message)."""
        try:
            tree = self.parser.parse(formula)
            return True, "Formula is valid"
        except Exception as e:
            return False, f"Syntax error: {str(e)[:200]}"

    def evaluate(self, formula: str, df: pd.DataFrame, target_idx: int) -> bool:
        """Evaluate TDX formula on stock data at target date index.

        Args:
            formula: TDX formula text
            df: Stock DataFrame with English columns (date, open, close, high, low, volume, amount)
            target_idx: Row index of the screening date

        Returns:
            True if the stock matches the formula at target_idx
        """
        try:
            tree = self.parser.parse(formula)
        except Exception as e:
            logger.warning(f"TDX parse error: {e}")
            return False

        # Build evaluation context
        context = {
            "CLOSE": df["close"].astype(float),
            "OPEN": df["open"].astype(float),
            "HIGH": df["high"].astype(float),
            "LOW": df["low"].astype(float),
            "VOL": df["volume"].astype(float),
            "VOLUME": df["volume"].astype(float),
            "AMOUNT": df["amount"].astype(float),
            # Aliases
            "C": df["close"].astype(float),
            "O": df["open"].astype(float),
            "H": df["high"].astype(float),
            "L": df["low"].astype(float),
            "V": df["volume"].astype(float),
        }

        try:
            evaluator = TDXEvaluator(context)
            result = evaluator.transform(tree)

            if result is None:
                return False

            # Extract value at target index
            if isinstance(result, pd.Series):
                if target_idx < len(result):
                    val = result.iloc[target_idx]
                    if pd.isna(val):
                        return False
                    return bool(val)
                return False
            elif isinstance(result, tuple):
                # Composite indicator: use first element
                first = result[0]
                if isinstance(first, pd.Series) and target_idx < len(first):
                    val = first.iloc[target_idx]
                    return bool(val) if not pd.isna(val) else False
                return False
            else:
                return bool(result)
        except Exception as e:
            logger.warning(f"TDX eval error: {e}")
            return False
