# Hermes Agent FSI Skills

> 金融服务业（Financial Services Industry）技能集合 — 运行在 [Hermes Agent](https://hermes-agent.nousresearch.com) 框架下的 A 股/美股/港股/外汇/板块行情速查工具集。

## 目录结构

```
fsi/
├── global-market/          # 全球金融市场速查技能
│   ├── SKILL.md            # 技能定义文档（版本 1.1.0）
│   ├── scripts/
│   │   └── run.py          # 主查询脚本（个股/基金/外汇/指数/板块/K线图）
│   ├── charts/             # 运行时生成的K线图（自动创建）
│   │   └── *.png           # 按参数动态命名，如 002938_K120_MA20_MA45_MA120.png
│   ├── assets/             # 静态资源
│   │   └── stock-chart-preview.png  # 个股K线效果预览图
│   └── references/
│       ├── charting.md         # matplotlib K线图生成参考
│       ├── csi-indices.md      # CSI 中证指数（H-series）数据源
│       ├── datasource-reference.md  # 各数据源字段详解
│       ├── environment.md      # 腾讯云环境适配说明
│       ├── fund-api.md         # 天天基金净值 API
│       ├── ifzq-api.md         # Tencent ifzq API（A股/港股历史K线）
│       ├── nasdaq-api.md       # 新浪美股 API（指数历史）
│       ├── sector-mapping.md   # A股板块名称映射表
│       └── us-futures-sources.md  # 美股期货数据源排查记录
└── README.md               # 本文件
```

## 技能列表

### 1. global-market — 全球金融市场速查

**版本：** v1.1.0

一键查询 A 股、美股、港股、外汇、基金的实时行情，以及 A 股概念/行业板块涨跌幅，自动识别市场并路由到对应数据源。支持**个股K线趋势图**（可自定义K线天数和均线列表），K线颜色遵循各地惯例（亚洲红涨绿跌 / 欧美绿涨红跌）。

#### 核心功能

| 功能 | 命令 | 数据源 |
|------|------|--------|
| 个股行情（A 股/美股/港股） | `run.py <代码或名称>` | 腾讯行情/新浪港股 |
| 基金净值（自动兜底） | `run.py <6位基金代码>` | 天天基金 |
| 外汇汇率 | `run.py 汇率美元 / USD/CNY` | open.er-api.com |
| 美股指数历史分析 | `run.py --history NDX/SPX/DJI/COMP` | 新浪美股 |
| 指数K线图 | `run.py --history SPX --chart` | matplotlib |
| **个股K线趋势图** | **`run.py 600519 --chart` / 动态参数** | **Tencent ifzq / 新浪美股** |
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

#### 美股指数历史分析 + K线图

```bash
run.py --history NDX         # NASDAQ-100 近一个月走势分析
run.py --history SPX --chart # S&P 500 走势分析 + K线图
run.py --history DJI         # 道琼斯
run.py --history COMP        # NASDAQ Composite
```

输出：文字分析（周涨跌幅、最大回撤、区间振幅）+ 图片存入 `charts/` 文件夹，如 `NDX_history.png`。

#### 收盘日报（定时推送·微信友好）

交易日 15:30 CST 自动推送 A股概念+行业混合排名的涨跌幅 TOP10，直接发到聊天窗口。专为微信阅读优化——纯文本格式，无 markdown 表格，无 box-drawing 字符。

**推送示例：**

```
📊 A股板块收盘日报 — 05月22日(Fri)

📈 涨幅 TOP 10（概念+行业混合）
  1. 培育钻石(概念) 📈 +7.24%
  2. PCB概念(概念) 📈 +6.33%
  3. 同花顺果指数(概念) 📈 +5.67%
  ...

📉 跌幅 TOP 10（概念+行业混合）
  1. 酿酒行业(行业) 📉 -1.80%
  2. 白酒概念(概念) 📉 -0.98%
  ...

📋 概览：概念387个+行业49个｜上涨413 下跌22 平盘1
```

- schedule: `30 15 * * 1-5`（周一到周五）
- job_id: `b6fd5bdf327c`
- data source：同花顺资金流向概念（~387个）+ 新浪行业（~49个），混合排序
- ETF推荐：每个板块自动匹配对应主题ETF（如 CPO→通信ETF），展示ETF实时涨跌幅
- 板块→ETF映射表见 `global-market/references/etf-mapping.md`

#### 批量查询

逗号分隔多条件，自动路由到不同市场：
```bash
run.py "茅台,AAPL,00700,USD/CNY"
```

#### 环境适配

专为腾讯云环境优化 — 规避了东方财富 API 的拦截。实时行情走腾讯行情（`qt.gtimg.cn`）/ 新浪港股（`hq.sinajs.cn`），历史K线走 Tencent ifzq API（`web.ifzq.gtimg.cn`）和 新浪美股 US_MinKService API。仅依赖 `requests` 和 `akshare`。

## 使用前提

- **Python 环境：** 需要 `akshare`, `requests`（图表功能需 `matplotlib`, `numpy`）；中文字体需 `WenQuanYi Zen Hei`
- **数据来源：** 所有数据通过公开 HTTP API 获取，无需 API Key

## 迭代计划

该目录将逐步扩展更多 FSI 相关技能，包括但不限于：
- 股票扫描器（技术面/基本面选股）
- 价格监控（目标价提醒）
- 更多市场数据接入
