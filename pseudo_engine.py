"""Chinese pseudo-code formula translator -> Python expressions."""

import re
import logging

from python_engine import PythonEngine

logger = logging.getLogger(__name__)

# Chinese keyword -> Python replacement
KEYWORD_MAP = {
    "收盘价": "close",
    "收盘": "close",
    "开盘价": "open",
    "开盘": "open",
    "最高价": "high",
    "最高": "high",
    "最低价": "low",
    "最低": "low",
    "成交量": "vol",
    "量": "vol",
    "成交额": "amount",
    "换手率": "turnover",
    "大于": ">",
    "小于": "<",
    "等于": "==",
    "不等于": "!=",
    "大于等于": ">=",
    "小于等于": "<=",
    "并且": " and ",
    "而且": " and ",
    "同时": " and ",
    "且": " and ",
    "或者": " or ",
    "或": " or ",
}


class PseudoEngine:
    """Translates Chinese pseudo-code to Python and evaluates."""

    def __init__(self):
        self.python_engine = PythonEngine()

    def translate(self, formula: str) -> str:
        """Convert Chinese pseudo-code to Python expression."""
        text = formula.strip()

        # 1. N日均线 -> ma(close, N)
        text = re.sub(r"(\d+)日均线", r"ma(close, \1)", text)
        # N日均量 -> ma(vol, N)
        text = re.sub(r"(\d+)日均量", r"ma(vol, \1)", text)
        # N日最高 -> hhv(high, N)
        text = re.sub(r"(\d+)日最高", r"hhv(high, \1)", text)
        # N日最低 -> llv(low, N)
        text = re.sub(r"(\d+)日最低", r"llv(low, \1)", text)
        # N日新高 -> close == hhv(close, N)
        text = re.sub(r"(\d+)日新高", r"(close == hhv(close, \1))", text)
        # N日新低 -> close == llv(close, N)
        text = re.sub(r"(\d+)日新低", r"(close == llv(close, \1))", text)

        # 2. 上穿 / 金叉: A 上穿 B -> cross(A, B)
        text = re.sub(
            r"(\S+)\s*上穿\s*(\S+)",
            lambda m: f"cross({m.group(1)}, {m.group(2)})",
            text,
        )
        text = re.sub(
            r"(\S+)\s*金叉\s*(\S+)",
            lambda m: f"cross({m.group(1)}, {m.group(2)})",
            text,
        )
        # 下穿 / 死叉: A 下穿 B -> cross(B, A)
        text = re.sub(
            r"(\S+)\s*下穿\s*(\S+)",
            lambda m: f"cross({m.group(2)}, {m.group(1)})",
            text,
        )
        text = re.sub(
            r"(\S+)\s*死叉\s*(\S+)",
            lambda m: f"cross({m.group(2)}, {m.group(1)})",
            text,
        )

        # 3. 昨日X -> ref(X, 1)
        text = re.sub(
            r"昨日(\S+)",
            lambda m: f"ref({KEYWORD_MAP.get(m.group(1), m.group(1))}, 1)",
            text,
        )
        text = re.sub(
            r"前日(\S+)",
            lambda m: f"ref({KEYWORD_MAP.get(m.group(1), m.group(1))}, 2)",
            text,
        )

        # 4. Direct keyword substitution (longer phrases first)
        for cn, py in sorted(KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
            text = text.replace(cn, py)

        # 5. 倍 -> *  (e.g., "2倍" -> "* 2")
        text = re.sub(r"(\d+(?:\.\d+)?)\s*倍", r"* \1", text)

        # 6. Clean up extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def validate(self, formula: str) -> tuple:
        """Validate by translating then checking Python syntax."""
        try:
            translated = self.translate(formula)
            valid, msg = self.python_engine.validate(translated)
            if valid:
                return True, f"Translated: {translated}"
            return False, f"Translation error: {msg} (translated: {translated})"
        except Exception as e:
            return False, f"Translation failed: {str(e)}"

    def evaluate(self, formula: str, df, target_idx: int) -> bool:
        """Translate pseudo-code to Python and evaluate."""
        try:
            translated = self.translate(formula)
            return self.python_engine.evaluate(translated, df, target_idx)
        except Exception as e:
            logger.warning(f"Pseudo eval error: {e}")
            return False
