# A股选股平台 v1.2

基于公式驱动的A股选股回测平台。支持通达信公式、Python表达式和中文伪代码三种选股语法，自带K线图表、收益统计和策略管理。

## 快速开始

### 环境要求
- Python 3.10+
- 网络连接（首次安装依赖 + AKShare 数据源）

### 启动

**macOS / Linux:**
```bash
./start.sh
```

**Windows:**
```
双击 start.bat
```

**手动启动:**
```bash
pip install -r requirements.txt
python3 app.py
```

启动后浏览器访问 **http://localhost:8080**

## 功能说明

### 三种选股公式

| 类型 | 示例 |
|------|------|
| 通达信公式 | `CROSS(MA(CLOSE, 5), MA(CLOSE, 10))` |
| Python | `cross(ma(close, 5), ma(close, 10))` |
| 中文伪代码 | `5日均线 上穿 10日均线` |

### 内置指标
MA, EMA, SMA, MACD, KDJ, RSI, BOLL, ATR, DMI, WR, BIAS, CCI, OBV, TRIX 等

### 通达信公式语法
- 变量赋值: `X := MA(CLOSE, 5);`
- 输出选股: `CROSS(X, MA(CLOSE, 10));`
- 支持: CROSS, LONGCROSS, REF, HHV, LLV, COUNT, BARSLAST, EVERY, EXIST, IF, MAX, MIN, ABS

### 功能清单
- **选股引擎** — 输入公式 + 选股日期，扫描全部A股
- **K线图表** — 点击结果查看个股K线，标注选股日，涨停板黄色高亮
- **收益统计** — 3/5/10/20日平均收益、胜率、收益分布直方图
- **策略管理** — 保存、加载、编辑、删除选股策略
- **数据更新** — 一键批量更新全部股票历史数据
- **CSV导出** — 一键导出选股结果

### 数据说明
- 数据源: AKShare（前复权日K线）
- 离线模式: 无法连接AKShare时自动切换为模拟数据（50只代表性股票）
- 缓存目录: `data_cache/`，可删除后重新拉取

## 文件结构

```
├── app.py              # FastAPI 服务主入口
├── models.py           # 数据模型定义
├── indicators.py       # 技术指标计算（MA/EMA/MACD/KDJ/RSI/BOLL...）
├── tdx_engine.py       # 通达信公式解析引擎（Lark语法）
├── python_engine.py    # Python表达式安全执行引擎
├── pseudo_engine.py    # 中文伪代码翻译引擎
├── formula_library.py  # 内置公式模板库
├── data_layer.py       # 数据获取/缓存/归一化
├── mock_data.py        # 模拟数据生成器
├── performance.py      # 收益计算与统计
├── requirements.txt    # Python依赖
├── start.sh            # Linux/macOS 启动脚本
├── start.bat           # Windows 启动脚本
├── static/
│   └── index.html      # 前端页面
└── data_cache/         # 运行时数据缓存（可删除）
```

## 注意事项

- 本平台仅供学习研究使用，不构成任何投资建议
- 模拟数据基于随机生成，与真实行情无关
- AKShare 数据源为免费公开接口，高频调用可能受限
