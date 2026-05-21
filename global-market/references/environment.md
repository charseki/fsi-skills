# 环境依赖

此 FSI 技能家族（global-market, stock-scanner, price-monitor）共享同一 Python 环境。

## 虚拟环境

```
路径: ~/venv/
Python: 3.11
创建原因: 系统 Python 为 externally-managed (PEP 668)
激活: source ~/venv/bin/activate
直接运行: ~/venv/bin/python3 script.py
```

## 必要包

| 包名 | 用途 | 安装命令 |
|------|------|----------|
| requests | **必需** — 所有行情 API 调用 | `~/venv/bin/pip install requests` |
| akshare | **可选但推荐** — A股板块行情 (`--sector` 模式必需) | `~/venv/bin/pip install akshare` |

### 其他可选包

| 包名 | 用途 | 安装命令 |
|------|------|----------|
| matplotlib | K线图生成（--chart 模式） | `~/venv/bin/pip install matplotlib numpy` |

## 云环境注意事项 (Tencent Cloud)

此环境（Tencent Cloud / 腾讯云）存在以下限制：

| 目标 | 状态 | 替代方案 |
|------|------|----------|
| EastMoney (东方财富) — `*_em` akshare 函数 | ❌ 连接被拒绝 | ✅ 腾讯行情 qt.gtimg.cn |
| Yahoo Finance — yfinance 数据源 | ❌ HTTP 429 限流 | ✅ 腾讯行情 qt.gtimg.cn |
| Nasdaq 官方 API (api.nasdaq.com) | ❌ 仅 NDX/COMP 可用，SPX/DJI 404 | ✅ 新浪美股 API (v2.2.0+) |
| Sina Finance (suggest3 / hq) | ✅ 正常（需 Referer header） | — |
| open.er-api.com | ✅ 正常 | — |
| 天天基金 (fundgz.1234567.com.cn) | ✅ 正常 | — |
| 同花顺 fund_flow_concept (通过 akshare) | ✅ 正常（387 个概念） | — |
| Sina 概念/行业 sector_spot (通过 akshare) | ✅ 正常（175 概念 + 49 行业） | — |

## 数据源映射汇总 (v1.0.0)

| 市场 | 主要数据源 | 备选 |
|------|-----------|------|
| A 股行情 | `qt.gtimg.cn/q=sh{code}` / `q=sz{code}` | — |
| A 股名称搜索 | `suggest3.sinajs.cn` (新浪) | — |
| 基金净值兜底 | `fundgz.1234567.com.cn/js/{code}.js` | — |
| 美股行情 | `qt.gtimg.cn/q=us{symbol}` | — |
| 美股指数 (NDX/SPX/DJI) 快照 | `qt.gtimg.cn` (SPX→usINX, DJI→us.DJI) | — |
| 美股指数历史 (NDX/SPX/DJI/COMP) | 新浪美股 `US_MinKService.getDailyK` | — |
| 港股行情 | `hq.sinajs.cn/list=hk{code}` (需 Referer) | — |
| 外汇 | `open.er-api.com/v6/latest/{base}` | — |
| **概念板块行情** | `ak.stock_fund_flow_concept()` | `ak.stock_sector_spot(indicator='概念')` |
| **行业板块行情** | `ak.stock_sector_spot(indicator='新浪行业')` | — |
