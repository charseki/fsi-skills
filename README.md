# Hermes Agent FSI Skills

> 金融服务业（Financial Services Industry）技能集合 — 运行在 [Hermes Agent](https://hermes-agent.nousresearch.com) 框架下的 A 股/美股/港股/外汇/板块行情速查工具集。

## 目录结构

```
fsi/
├── global-market/          # 全球金融市场速查技能
│   ├── SKILL.md            # 技能定义文档（版本 1.1.0）
│   ├── scripts/
│   │   ├── run.py              # 主查询脚本（个股/基金/外汇/指数/板块/K线图/回撤折线图）
│   │   └── build-fund-mapping.py  # 板块→基金映射构建脚本
│   ├── charts/                 # 运行时生成的K线图 + 回撤折线图（自动创建，gitignored）
│   │   └── *.png               # 按参数动态命名，如 002938_K120_MA20_MA45_MA120.png / 007467_HC30.png
│   ├── assets/                 # 静态资源
│   │   └── stock-chart-preview.png  # 个股K线效果预览图
│   └── references/
│       ├── charting.md             # matplotlib K线图生成参考
│       ├── csi-indices.md          # CSI 中证指数（H-series）数据源
│       ├── datasource-reference.md # 各数据源字段详解
│       ├── environment.md          # 腾讯云环境适配说明
│       ├── etf-mapping.md          # 板块→主题基金映射表（37板块48基金，含多周期涨跌幅）
│       ├── fund-api.md             # 天天基金净值 API
│       ├── fund-nav-history.csv    # 全部基金历史净值数据（51764+条）
│       ├── ifzq-api.md             # Tencent ifzq API（A股/港股历史K线）
│       ├── lof-mapping.md          # 用户提供的板块→LOF/联接基金原始映射
│       ├── nasdaq-api.md           # 新浪美股 API（指数历史 + 个股历史）
│       ├── sector-mapping.md       # A股板块名称映射表
│       ├── technical-analysis.md   # 金叉/死叉/MACD量化分析脚本
│       └── us-futures-sources.md   # 美股期货数据源排查记录
├── price-monitor/           # 量化交易策略引擎（v1.0.0）
│   ├── SKILL.md             # 技能定义文档
│   ├── core/
│   │   ├── market_data.py   # 统一数据获取层（A股/美股/港股/基金）
│   │   ├── portfolio.py     # 持仓管理（增删改查+快照+交易历史）
│   │   └── run.py           # 主调度引擎（全量扫描+策略编排+汇总报告）
│   ├── strategies/
│   │   ├── base.py               # 策略基类 (BaseStrategy + Signal)
│   │   ├── drawdown_rebalance.py # 回撤再平衡：回撤加仓+反弹减仓
│   │   ├── golden_cross.py       # 金叉死叉：多组均线对交叉检测
│   │   ├── ma_strategy.py        # 均线排列：多头/空头+超买超卖
│   │   └── drawdown_personal.py  # 个人回撤加仓：3%/5%/8%/10%+固定金额阶梯
│   ├── config/
│   │   ├── symbols.yaml     # 监控标的列表（14个标的）
│   │   └── strategies.yaml  # 策略参数配置（4个策略）
│   ├── reports/
│   │   ├── signals/         # 扫描报告（JSON）
│   │   └── snapshots/       # 持仓快照（JSON）
│   ├── scripts/
│   │   ├── scan.py          # Hermes入口脚本
│   │   └── daily_personal.py# 个人策略每日监控脚本
│   └── examples/
│       └── quickstart.py    # 快速上手演示
└── README.md               # 本文件
```

## 技能列表

### 1. global-market — 全球金融市场速查

**版本：** v1.1.0

一键查询 A 股、美股、港股、外汇、基金的实时行情，以及 A 股概念/行业板块涨跌幅，自动识别市场并路由到对应数据源。支持**个股K线趋势图**（可自定义K线天数和均线列表）和**回撤折线图 (HC)**，K线颜色遵循各地惯例（亚洲红涨绿跌 / 欧美绿涨红跌）。

#### 核心功能

| 功能 | 命令 | 数据源 |
|------|------|--------|
| 个股行情（A 股/美股/港股） | `run.py <代码或名称>` | 腾讯行情/新浪港股 |
| 基金净值（自动兜底） | `run.py <6位基金代码>` | 天天基金 |
| 外汇汇率 | `run.py 汇率美元 / USD/CNY` | open.er-api.com |
| 美股指数历史分析 | `run.py --history NDX/SPX/DJI/COMP` | 新浪美股 |
| 指数K线图 | `run.py --history SPX --chart` | matplotlib |
| **个股K线趋势图** | **`run.py 600519 --chart` / 动态参数** | **Tencent ifzq / 新浪美股** |
| **回撤折线图 (HC)** | **`run.py "007467,HC30"` / `"茅台,HC30"`** | **akshare 基金净值 / ifzq** |
| 概念板块涨跌幅 | `run.py --sector "CPO,机器人,存储芯片"` | 同花顺资金流向 |
| 行业板块排行 | `run.py --sector all --industry` | 新浪行业 |
| 板块速览 | `run.py --sector all --top5` | 同花顺资金流向 |

#### 个股K线趋势图

A股/美股/港股查询时加 `--chart` 或使用动态参数格式 `<股票>,K<天数>,[MA<周期>,...]` 均可生成K线趋势图，K线天数和均线列表灵活自定义：

```bash
# 默认：90日K线 + MA20/MA90
run.py 600519 --chart
run.py AAPL --chart

# 自定义K线天数 + 均线列表（逗号分隔，无需 --chart）
run.py "002938,K120,[MA20,MA45,MA120]"
run.py "茅台,K60,[MA10,MA20]"
run.py "AAPL,[MA50,MA100,MA200]"
run.py "00700,K200"
```

- `--chart` 不传动态参数时使用默认值（90日 + MA20/MA90）
- 传入动态参数时自动取代默认值（`--chart` 可省略）
- K线天数不足时按实际可用天数展示；均线周期大于数据长度时自动跳过
- K线颜色：A股/港股 **红涨绿跌**（亚洲惯例），美股 **绿涨红跌**（欧美惯例）
- 成交量柱：A股自动换算为 **成交额(百万元)**（手数 × 收盘价 / 10000）

**实际运行效果（鹏鼎控股 002938, 120日K线, MA20+MA45+MA120）：**

![stock-chart-preview](global-market/assets/stock-chart-preview.png)

**数据源：** A股/港股历史K线 → Tencent ifzq API（前复权，`web.ifzq.gtimg.cn`），美股历史 → 新浪 US_MinKService API。

#### 回撤折线图 (HC — Drawdown)

输入 `<代码>,HC<N>` 生成近 N 个交易日（基金用单位净值，股票用前复权收盘价）的回撤折线图，自动标注最大回撤点和当前回撤：

```bash
# 基金回撤（30个交易日）
run.py "007467,HC30"      # 华泰柏瑞红利低波联接C 30日回撤

# 基金回撤（90个交易日 ≈ 3个月）
run.py "013275,HC90"      # 富国中证煤炭C 90日回撤

# A 股回撤
run.py "600519,HC30"      # 茅台 30日回撤
run.py "茅台,HC30"         # 名称搜索自动解析

# 美股 / 港股回撤
run.py "AAPL,HC60"        # Apple 60日回撤
run.py "00700,HC30"       # 腾讯 30日回撤
```

- 基金走 `akshare.fund_open_fund_info_em()` 历史净值，股票走 Tencent ifzq / 新浪 K 线
- 6 位数字自动先试基金再试 A 股，无需手动指定类型
- 输出至 `charts/{code}_HC{days}.png`（暗色主题，~100-180KB, 150dpi）
- 同时输出文字摘要：当前回撤 + 区间最大回撤百分比
- 支持中英文逗号：`"007467,HC30"` / `"007467，HC30"`

#### 美股指数历史分析 + K线图

```bash
run.py --history NDX         # NASDAQ-100 近一个月走势分析
run.py --history SPX --chart # S&P 500 走势分析 + K线图
run.py --history DJI         # 道琼斯
run.py --history COMP        # NASDAQ Composite
```

输出：文字分析（周涨跌幅、最大回撤、区间振幅）+ 图片存入 `charts/` 文件夹，如 `NDX_history.png`。

#### 收盘日报（定时推送·微信友好）

交易日 15:30 CST 自动推送 A股概念+行业混合排名的涨跌幅 TOP10。数据源已切换为**基金净值体系**（基于 lof-mapping.md 的 37板块48只基金），每只板块自动匹配对应主题基金的**净值涨跌幅**推荐。

专为微信阅读优化——纯文本格式，无 markdown 表格，无 box-drawing 字符。

**推送示例：**

```
📊 A股板块基金收盘日报 — 05月26日(Mon)

📈 涨幅 TOP 10
  1. 共封装光学(CPO)(概念) 📈 +5.29%
         🏷️ 永赢科技智选混合发起C(022365) 📈 +1.82%
  2. 半导体(概念) 📈 +4.89%
         🏷️ 永赢半导体产业智选混合发起C(015968) 📈 +0.70%
  3. 存储芯片(概念) 📈 +3.21%
         🏷️ 广发远见智选混合C(016874) 📉 -3.05%
  4. 5G(概念) 📈 +3.08%
         🏷️ 安信新回报混合C(002771) 📈 +0.53%
  5. 军工(概念) 📈 +2.76%
         🏷️ 华夏军工安全混合C(013566) 📉 -0.83%
  6. 稀土永磁(概念) 📈 +2.14%
         🏷️ 嘉实中证稀土产业ETF联接C(011036) 📈 +0.23%
  7. 消费电子(概念) 📈 +1.98%
         🏷️ 易方达中证消费电子主题ETF发起式联接C(018897) 📉 -0.13%
  8. 煤炭概念(概念) 📈 +1.87%
         🏷️ 富国中证煤炭指数C(013275) 📉 -0.98%
  9. 有色金属(概念) 📈 +1.65%
         🏷️ 富国资源精选混合发起式C(022167) 📈 +0.90%
  10. 钢铁(行业) 📈 +1.43%
         🏷️ 永赢资源慧选混合发起式C(025217) 📈 +3.70%

📉 跌幅 TOP 10
  1. 酿酒行业(行业) 📉 -1.80%
         🏷️ 招商中证白酒指数C(012414) 📉 -0.88%
  2. 白酒概念(概念) 📉 -1.54%
         🏷️ 招商中证白酒指数C(012414) 📉 -0.88%
  3. 人工智能(概念) 📉 -1.23%
         🏷️ 博时移动互联混合C(012780) 📈 +0.59%
  4. 银行(概念) 📉 -0.98%
         🏷️ 天弘中证银行ETF联接C(001595) 📈 +0.22%
  5. 机器人概念(概念) 📉 -0.87%
         🏷️ 永赢先进制造智选混合发起C(018125) 📉 -1.09%
  6. 红利低波(概念) 📉 -0.72%
         🏷️ 华泰柏瑞中证红利低波ETF联接C(007467) 📈 +0.27%
  7. 港股创新药(概念) 📉 -0.65%
         🏷️ 永赢医药创新智选混合发起C(015916) 📉 -0.89%
  8. 黄金概念(概念) 📉 -0.50%
         🏷️ 国泰黄金ETF联接C(004253) 📉 -0.50%
  9. 交通运输(行业) 📉 -0.43%
         🏷️ 广发价值领先混合C(012420) 📈 +1.21%
  10. 锂电池概念(概念) 📉 -0.38%
         🏷️ 前海开源周期精选混合C(022447) 📈 +1.76%

📋 概览：概念387个+行业49个｜上涨256 下跌175 平盘5
    最高：共封装光学(CPO)(概念) +5.29% → 🏷️ 永赢科技智选混合发起C(022365) 📈 +1.82%
    最深：酿酒行业(行业) -1.80% → 🏷️ 招商中证白酒指数C(012414) 📉 -0.88%
```

- schedule: `30 15 * * 1-5`（周一到周五）
- job_id: `ea5281cb20ae`
- data source：同花顺资金流向概念（~387个）+ 新浪行业（~49个），混合排序 → FUND_MAP 映射到 lof-mapping 基金
- 基金净值推荐：每个板块自动匹配对应主题基金（如 CPO→022365 永赢科技），展示基金当日预估涨跌幅
- 板块→基金映射表见 `global-market/references/etf-mapping.md`
- 历史净值数据见 `global-market/references/fund-nav-history.csv`（51764条，用于回测统计）
- ⚠️ 板块涨跌与基金净值方向可能不一致（主动型基金持仓偏差），如实展示即可
- ⚠️ etf-mapping.md 为静态快照，收盘日报通过 fundgz API 实时获取盘中估算净值

#### 批量查询

逗号分隔多条件，自动路由到不同市场：
```bash
run.py "茅台,AAPL,00700,USD/CNY"
```

#### 环境适配

专为腾讯云环境优化 — 规避了东方财富 API 的拦截。实时行情走腾讯行情（`qt.gtimg.cn`）/ 新浪港股（`hq.sinajs.cn`），历史K线走 Tencent ifzq API（`web.ifzq.gtimg.cn`）和 新浪美股 US_MinKService API，基金历史净值走 akshare `fund_open_fund_info_em()`。仅依赖 `requests` 和 `akshare`。

---

### 2. price-monitor — 量化交易策略引擎

**版本：** v1.0.0

多策略扫描 + 信号生成 + 持仓管理。定时监控所有标的，运行多个量化策略，生成买入/卖出/加仓信号。策略可插拔，随时添加。

#### 内置策略

| 策略 | 文件名 | 逻辑 | 适用场景 |
|------|--------|------|----------|
| 回撤再平衡 | `drawdown_rebalance.py` | 回撤到档位加仓，从低点反弹减仓 | ETF定投管理 |
| 金叉死叉 | `golden_cross.py` | 5组均线对交叉检测，综合投票 | 趋势跟踪 |
| 均线排列 | `ma_strategy.py` | 多头/空头排列判断+超买超卖 | 趋势判断/过滤器 |
| **个人回撤加仓** | **`drawdown_personal.py`** | **3%/5%/8%/10%+阶梯，固定金额提醒** | **盯盘补仓** |

#### 核心命令

```bash
# 全量扫描（所有标的 × 所有策略）
source ~/venv/bin/activate && python3 core/run.py

# 只跑指定策略
python3 core/run.py --strategy drawdown-personal

# 只扫单个标的
python3 core/run.py --symbol 512890

# 评估当前持仓
python3 core/run.py --portfolio

# 添加持仓
python3 core/run.py --add-position 512890 红利低波ETF 1000 1.025

# 查看配置
python3 scripts/scan.py --list-symbols
python3 scripts/scan.py --list-strategies

# 快速演示
python3 examples/quickstart.py
```

#### 个人回撤加仓策略（你的专属策略）

基于回撤趋势变化判断——只在你注意到回撤**正在发生**时提醒，不回放历史深跌：

| 回撤幅度 | 操作 | 金额 |
|----------|------|------|
| 跌 3% | 轻度加仓 | +¥5,000 |
| 跌 5% | 中度加仓 | +¥10,000 |
| 跌 8% | 较大加仓 | +¥20,000 |
| 跌 10%+ | 观望等待 | 不加仓，仅提醒 |

- **趋势检测**：参考近10日回撤变化，只在回撤加深时触发
- **单次有效**：每个档位每个标的只触发一次，价格回升后自动重置
- **跨市场**：A股/ETF/美股/港股/基金全覆盖

**每日自动监控（cronjob）：**

```
schedule: 30 15 * * 1-5  (交易日 15:30 CST)
job_id:   45de32fd2b57
deliver:  推送到聊天窗口
```

**输出示例：**

```
📊 个人回撤监控日报 — 2026-06-01

  📈 科创50ETF (588000)  现价: 1.7500
     📉 +¥10,000 — 触发中度加仓档位(-5%)
     📉 +¥20,000 — 触发较大加仓档位(-8%)
     ⚠️ 建议观望不加仓

  📈 芯片ETF (159995)  现价: 2.3570
     📉 +¥5,000 — 触发轻度加仓档位(-3%)
     📉 +¥10,000 — 触发中度加仓档位(-5%)
     📉 +¥20,000 — 触发较大加仓档位(-8%)
     ⚠️ 建议观望不加仓

───
8 个信号 | 2026-06-01
```

#### 添加新策略（3步）

1. 在 `strategies/` 下新建 `.py` 文件，继承 `BaseStrategy` 实现 `evaluate()`
2. 在 `core/run.py` 的 `_load_strategy()` 中注册
3. 在 `config/strategies.yaml` 中添加配置

#### 配置说明

监控标的编辑 `config/symbols.yaml`，策略参数编辑 `config/strategies.yaml`。当前监控14个标的（宽基ETF + 行业ETF + 美股 + 个股）。

#### 数据源

复用 global-market 已验证的数据源：A股/港股走 Tencent ifzq + 新浪，美股走新浪 US_MinKService，基金走天天基金 + akshare。全部已适配腾讯云环境。

---

## 使用前提

- **Python 环境：** 需要 `akshare`, `requests`（图表功能需 `matplotlib`, `numpy`）；中文字体需 `WenQuanYi Zen Hei`
- **数据来源：** 所有数据通过公开 HTTP API 获取，无需 API Key

## 迭代计划

该目录将逐步扩展更多 FSI 相关技能，包括但不限于：
- 股票扫描器（技术面/基本面选股）✅ v1.0.0 已建目录
- 价格监控（目标价提醒）✅ v1.0.0 已完成（量化策略引擎）
- 更多市场数据接入
