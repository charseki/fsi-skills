# Hermes Agent FSI Skills

> 金融服务业（Financial Services Industry）技能集合 — 运行在 [Hermes Agent](https://hermes-agent.nousresearch.com) 框架下的 A 股/美股/港股/外汇/板块行情速查工具集。

## 目录结构

```
fsi/
├── global-market/          # 全球金融市场速查技能
│   ├── SKILL.md            # 技能定义文档（版本 1.0.0）
│   ├── scripts/
│   │   └── run.py          # 主查询脚本（个股/基金/外汇/指数/板块）
│   └── references/
│       ├── charting.md         # matplotlib K线图生成参考
│       ├── csi-indices.md      # CSI 中证指数（H-series）数据源
│       ├── datasource-reference.md  # 各数据源字段详解
│       ├── environment.md      # 腾讯云环境适配说明
│       ├── fund-api.md         # 天天基金净值 API
│       ├── nasdaq-api.md       # 新浪美股 API（指数历史）
│       └── sector-mapping.md   # A股板块名称映射表
└── README.md               # 本文件
```

## 技能列表

### 1. global-market — 全球金融市场速查

**版本：** v1.0.0

一键查询 A 股、美股、港股、外汇、基金的实时行情，以及 A 股概念/行业板块涨跌幅，自动识别市场并路由到对应数据源。

#### 核心功能

| 功能 | 命令 | 数据源 |
|------|------|--------|
| 个股行情（A 股/美股/港股） | `run.py <代码或名称>` | 腾讯行情/新浪港股 |
| 基金净值 | `run.py <6位基金代码>`（自动兜底） | 天天基金 |
| 外汇汇率 | `run.py 汇率美元 / USD/CNY` | open.er-api.com |
| 美股指数历史 | `run.py --history NDX/SPX/DJI/COMP` | 新浪美股 |
| 指数K线图 | `run.py --history SPX --chart` | matplotlib |
| 概念板块涨跌幅 | `run.py --sector "CPO,机器人,存储芯片"` | 同花顺资金流向 |
| 行业板块排行 | `run.py --sector all --industry` | 新浪行业 |
| 板块速览 | `run.py --sector all --top5` | 同花顺资金流向 |

#### 批量查询

逗号分隔多条件，自动路由到不同市场：
```bash
run.py "茅台,AAPL,00700,USD/CNY"
```

#### 环境适配

专为腾讯云环境优化 — 仅依赖 `requests` 和 `akshare`，规避了腾讯云对东方财富 API 的拦截。A 股/美股走腾讯行情（`qt.gtimg.cn`），港股走新浪（`hq.sinajs.cn`）。

## 使用前提

- **Python 环境：** 需要 `akshare`, `requests`（图表功能需 `matplotlib`, `numpy`）
- **数据来源：** 所有数据通过公开 HTTP API 获取，无需 API Key（外汇汇率除外，但 open.er-api.com 免费无认证）

## 迭代计划

该目录将逐步扩展更多 FSI 相关技能，包括但不限于：
- 股票扫描器（技术面/基本面选股）
- 价格监控（目标价提醒）
- 更多市场数据接入
