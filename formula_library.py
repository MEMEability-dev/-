"""Pre-built formula templates for common screening patterns."""

FORMULA_TEMPLATES = {
    "tdx": [
        {
            "name": "MA金叉 (5日上穿10日)",
            "description": "5日均线上穿10日均线，短期趋势转多",
            "formula": "CROSS(MA(CLOSE, 5), MA(CLOSE, 10))"
        },
        {
            "name": "MACD金叉",
            "description": "DIF上穿DEA，经典买入信号",
            "formula": "DIF:=EMA(CLOSE, 12) - EMA(CLOSE, 26);\nDEA:=EMA(DIF, 9);\nCROSS(DIF, DEA)"
        },
        {
            "name": "MACD零轴下金叉",
            "description": "DIF在零轴下方上穿DEA，底部反转信号",
            "formula": "DIF:=EMA(CLOSE, 12) - EMA(CLOSE, 26);\nDEA:=EMA(DIF, 9);\nCROSS(DIF, DEA) AND DIF < 0"
        },
        {
            "name": "放量突破",
            "description": "成交量超过5日均量2倍，收盘创20日新高",
            "formula": "VOL > MA(VOL, 5) * 2 AND CLOSE = HHV(CLOSE, 20)"
        },
        {
            "name": "KDJ超卖金叉",
            "description": "K值低于20后金叉D值",
            "formula": "RSV:=(CLOSE-LLV(LOW,9))/(HHV(HIGH,9)-LLV(LOW,9))*100;\nK:=SMA(RSV,3,1);\nD:=SMA(K,3,1);\nCROSS(K, D) AND K < 20"
        },
        {
            "name": "布林下轨反弹",
            "description": "昨日触及布林下轨，今日收回轨内",
            "formula": "MID:=MA(CLOSE, 20);\nLOWER:=MID - 2 * STD(CLOSE, 20);\nREF(LOW, 1) < LOWER AND CLOSE > LOWER"
        },
        {
            "name": "缩量回调",
            "description": "价格回调但成交量萎缩，趋势延续信号",
            "formula": "CLOSE < REF(CLOSE, 1) AND VOL < MA(VOL, 5) * 0.6 AND CLOSE > MA(CLOSE, 20)"
        },
        {
            "name": "多头排列",
            "description": "MA5>MA10>MA20>MA60，多头趋势",
            "formula": "MA(CLOSE,5) > MA(CLOSE,10) AND MA(CLOSE,10) > MA(CLOSE,20) AND MA(CLOSE,20) > MA(CLOSE,60)"
        },
        {
            "name": "底部十字星",
            "description": "近期下跌后出现十字星形态",
            "formula": "ABS(CLOSE - OPEN) < (HIGH - LOW) * 0.1 AND HIGH - LOW > 0 AND CLOSE < MA(CLOSE, 20) AND COUNT(CLOSE < REF(CLOSE, 1), 5) >= 3"
        },
        {
            "name": "RSI超卖",
            "description": "RSI低于30，超卖区域",
            "formula": "LC:=REF(CLOSE,1);\nRSI1:=SMA(MAX(CLOSE-LC,0),14,1)/SMA(ABS(CLOSE-LC),14,1)*100;\nRSI1 < 30"
        },
    ],
    "python": [
        {
            "name": "MA Golden Cross",
            "description": "5-day MA crosses above 10-day MA",
            "formula": "cross(ma(close, 5), ma(close, 10))"
        },
        {
            "name": "Volume Breakout",
            "description": "Volume > 2x average, new 20-day high",
            "formula": "(vol > ma(vol, 5) * 2) & (close == hhv(close, 20))"
        },
        {
            "name": "MACD Golden Cross",
            "description": "DIF crosses above DEA",
            "formula": "dif, dea, hist = macd(close)\ncross(dif, dea)"
        },
        {
            "name": "Price Above All MAs",
            "description": "Close above MA5, MA10, MA20",
            "formula": "(close > ma(close, 5)) & (close > ma(close, 10)) & (close > ma(close, 20))"
        },
        {
            "name": "Oversold RSI Bounce",
            "description": "RSI crosses above 30 from below",
            "formula": "rsi_val = rsi(close, 14)\ncross(rsi_val, pd.Series(30, index=close.index))"
        },
    ],
    "pseudo": [
        {
            "name": "均线金叉",
            "description": "5日均线上穿10日均线",
            "formula": "5日均线 上穿 10日均线"
        },
        {
            "name": "放量上涨",
            "description": "成交量放大且价格上涨",
            "formula": "收盘价 大于 昨日收盘价 且 成交量 大于 昨日成交量 * 1.5"
        },
        {
            "name": "创新高",
            "description": "收盘价创20日新高",
            "formula": "20日新高"
        },
        {
            "name": "缩量回调",
            "description": "价格回调但量能萎缩",
            "formula": "收盘价 小于 昨日收盘价 且 成交量 小于 昨日成交量 * 0.6"
        },
    ],
}
