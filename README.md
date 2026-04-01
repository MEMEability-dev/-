# A股选股平台 

一个面向学习与研究的 A 股选股与回测平台。用于验证主观策略是否可行。
支持通达信公式、Python 表达式、中文伪代码三种策略语法，提供 K 线查看、收益统计、策略管理和结果导出功能。

## 功能亮点

1. 三种策略语法统一入口，降低使用门槛
2. 支持按日期执行全市场选股扫描
3. 内置常用技术指标与收益统计分析
4. 支持策略保存、加载、编辑、删除
5. 支持结果 CSV 导出，方便二次分析

## 快速开始

### 环境要求

1. Python 3.9 及以上
2. 可联网环境（首次安装依赖和拉取行情数据）

### 启动方式

#### macOS（推荐）

直接双击 `A股选股平台.command`。

说明：`.command` 是 macOS 的可执行脚本入口，Windows 和 Linux 不能直接双击运行该文件。

#### Windows

双击 `start.bat`。

#### Linux / macOS 终端方式

```bash
./start.sh
```

#### 手动启动

```bash
pip install -r requirements.txt
python3 app.py
```

启动后访问：`http://localhost:8080`

## 使用流程

1. 选择策略语法（通达信 / Python / 中文伪代码）
2. 输入策略公式和选股日期
3. 执行选股并查看结果列表
4. 点击个股查看 K 线与后续表现
5. 按需导出结果

## 策略语法示例

| 类型 | 示例 |
|---|---|
| 通达信公式 | `CROSS(MA(CLOSE, 5), MA(CLOSE, 10))` |
| Python 表达式 | `cross(ma(close, 5), ma(close, 10))` |
| 中文伪代码 | `5日均线 上穿 10日均线` |

## 内置指标

MA, EMA, SMA, MACD, KDJ, RSI, BOLL, ATR, DMI, WR, BIAS, CCI, OBV, TRIX 等。

## 项目结构

```text
├── app.py                # FastAPI 服务入口
├── data_layer.py         # 数据获取、缓存、归一化
├── indicators.py         # 技术指标计算
├── tdx_engine.py         # 通达信公式解析引擎
├── python_engine.py      # Python 表达式执行引擎
├── pseudo_engine.py      # 中文伪代码翻译引擎
├── formula_library.py    # 内置公式模板
├── performance.py        # 收益统计
├── mock_data.py          # 模拟数据
├── models.py             # 数据模型
├── static/
│   └── index.html        # 前端页面
├── A股选股平台.command    # macOS 一键启动入口
├── start.sh              # Linux/macOS 启动脚本
├── start.bat             # Windows 启动脚本
└── data_cache/           # 本地行情缓存（可删除后重新拉取）
```

## 数据说明

1. 数据源：AKShare（前复权日线）
2. 缓存目录：`data_cache/`
3. 无法连接数据源时会自动回退到模拟数据

## 注意事项

1. 本项目仅供学习与研究使用，不构成投资建议
2. 请勿将本项目结果作为唯一投资依据
3. AKShare 为公开数据接口，频繁调用可能受限
