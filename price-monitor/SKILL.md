---
name: price-monitor
description: 量化交易策略引擎 — 多策略扫描+信号生成+持仓管理，支持回撤再平衡/金叉死叉/均线排列等策略，可插拔扩展
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [finance, quant, trading, fsi, strategy]
    category: fsi
    requires_toolsets: [terminal, file]
---

# price-monitor — 量化交易策略引擎

## 目录结构

```
price-monitor/
├── SKILL.md                   # 技能定义文档
├── core/
│   ├── __init__.py
│   ├── market_data.py         # 🎯 统一数据获取层（封装global-market已验证的数据源）
│   ├── portfolio.py           # 🎯 持仓管理（增删改查+快照+交易历史）
│   └── run.py                 # 🎯 主调度引擎（全量扫描+汇总报告）
├── strategies/
│   ├── __init__.py
│   ├── base.py                # 🎯 策略基类（BaseStrategy + Signal数据类）
│   ├── drawdown_rebalance.py  # ✅ 回撤再平衡：回撤加仓+反弹减仓
│   ├── drawdown_personal.py   # ✅ 个人回撤加仓：趋势判断+固定金额
│   ├── golden_cross.py        # ✅ 金叉死叉：多组均线对交叉检测
│   ├── ma_strategy.py         # ✅ 均线排列：多头/空头排列+超买超卖
│   └── __pycache__/
│   ├── symbols.yaml           # 🎯 监控标的列表（在此添加/删除标的）
│   └── strategies.yaml        # 🎯 策略参数配置（在此调整各策略参数）
├── reports/
│   ├── signals/               # 扫描报告输出（JSON格式）
│   └── snapshots/             # 持仓快照（JSON格式）
├── scripts/
│   ├── scan.py                # Hermes入口脚本（等同 core/run.py）
│   └── __init__.py
└── examples/
    └── quickstart.py          # 快速上手演示
```

## When to Use

- 用户说「跑一下量化扫描」「看看有什么信号」「策略扫描一下」
- 用户说「查持仓」「看盈亏」「组合评估」
- 用户说「设个策略」「配置监控」「加仓减仓信号」
- 用户想添加新的量化交易策略

## 已有的策略

| 策略 | 文件名 | 逻辑 | 适用 |
|------|--------|------|------|
| 回撤再平衡 | `drawdown_rebalance.py` | 回撤到档位按持仓%加仓，反弹减仓 | ETF定投 |
| 金叉死叉 | `golden_cross.py` | 5组均线对交叉检测，综合投票 | 趋势跟踪 |
| 均线排列 | `ma_strategy.py` | 多头/空头排列判断+超买超卖 | 趋势判断/过滤器 |
| 个人回撤加仓 | `drawdown_personal.py` | 回撤趋势变化→3%/5%/8%/10%+固定金额加仓 | 盯盘补仓提醒 |

**注意**：`drawdown-rebalance`（通用）和 `drawdown-personal`（个人）是**两套独立策略**，可以同时运行。通用策略做定投管理，个人策略做盯盘补仓提醒。

## 核心用法

```bash
# 1. 全量扫描（所有标的 × 所有策略）
source ~/venv/bin/activate && python3 ~/.hermes/skills/fsi/price-monitor/core/run.py

# 2. 只跑指定策略
python3 ~/.hermes/skills/fsi/price-monitor/core/run.py --strategy drawdown-rebalance

# 3. 只扫单个标的
python3 ~/.hermes/skills/fsi/price-monitor/core/run.py --symbol 512890

# 4. 评估当前持仓
python3 ~/.hermes/skills/fsi/price-monitor/core/run.py --portfolio

# 5. 添加持仓
python3 ~/.hermes/skills/fsi/price-monitor/core/run.py --add-position 512890 红利低波ETF 1000 1.025

# 6. 输出JSON报告
python3 ~/.hermes/skills/fsi/price-monitor/core/run.py --json

# 7. 列表查看
python3 ~/.hermes/skills/fsi/price-monitor/scripts/scan.py --list-symbols
python3 ~/.hermes/skills/fsi/price-monitor/scripts/scan.py --list-strategies

# 8. 快速演示
python3 ~/.hermes/skills/fsi/price-monitor/examples/quickstart.py
```

## 回撤再平衡策略详解（你最常用的场景）

### 配置示例（strategies.yaml 已内置）

```yaml
- name: "drawdown-rebalance"
  enabled: true
  apply_to: "etf"
  params:
    lookback_days: 120
    # 四档阶梯加仓：回撤越深加仓越多
    add_thresholds:
      - [-5, 10]     # 回撤5% → 加仓10%
      - [-10, 15]    # 回撤10% → 加仓15%
      - [-15, 25]    # 回撤15% → 加仓25%
      - [-20, 40]    # 回撤20% → 加仓40%
    # 从回撤低点反弹50% → 减仓
    sell_recovery: 50
    min_interval_days: 5   # 同方向至少隔5个交易日
```

### 信号输出示例

```
📈 红利低波ETF (512890)
   回撤 -5.1%, 触发加仓档位 -5% → 建议加仓 10% 持仓

📈 酒ETF (512690)
   回撤 -21.1%, 触发加仓档位 -20% → 建议加仓 40% 持仓

🔴 煤炭ETF (515220)
   金叉死叉：死叉信号，1/3组均线对呈死叉
```

### 场景：回撤加仓+反弹减仓（你的核心需求）

| 场景 | 触发条件 | 信号 |
|------|----------|------|
| 小幅回撤 | 回撤 -5% ~ -10% | 轻度加仓 10% |
| 中度回撤 | 回撤 -10% ~ -15% | 适度加仓 15% |
| 较大回撤 | 回撤 -15% ~ -20% | 加仓 25%（越跌越买） |
| 深度回撤 | 回撤 > -20% | 重仓加仓 40% |
| 反弹减仓 | 从底部反弹 >50% | 减仓 20% 锁定利润 |

如果你想调整档位或比例，直接改 `config/strategies.yaml` 就行。

## 个人专属回撤加仓策略（drawdown-personal）

基于你的交易习惯定制的策略，区别于通用的回撤再平衡策略。

### 核心规则

| 回撤幅度 | 操作 | 金额 |
|----------|------|------|
| 跌 3% | 轻度加仓 | +¥5,000 |
| 跌 5% | 中度加仓 | +¥10,000 |
| 跌 8% | 较大加仓 | +¥20,000 |
| 跌 10%+ | 观望等待 | 不加仓，仅提醒 |

### 策略设计

- **基于回撤趋势变化**：只在你注意到回撤「正在发生」时提醒，不回放历史
- **每个档位只触发一次**：同一个标的的同一个档位不会重复报警
- **价格回升后自动重置**：当一个标的涨回峰值附近后，清空状态重新监控下一轮回撤
- **固定金额**：每次提醒给你具体的加仓金额（¥5K/¥10K/¥20K），方便直接操作

### 配置示例（strategies.yaml）

```yaml
- name: "drawdown-personal"
  enabled: true
  apply_to: "all"
  params:
    thresholds:
      - [-3, 5000, "轻度加仓"]
      - [-5, 10000, "中度加仓"]
      - [-8, 20000, "较大加仓"]
      - [-10, 0, "观望等待"]
    reset_at_pct: -1.0       # 回撤恢复到 -1% 时重置
    lookback_days: 250
    trend_days: 10           # 参考近10日回撤趋势判断"新"回撤
```

### 每日监控（cronjob）

交易日 15:30 CST 自动扫描，有信号自动推送：

```bash
# 手动测试
source ~/venv/bin/activate && python3 ~/.hermes/skills/fsi/price-monitor/scripts/daily_personal.py

# cronjob 信息
job_id: 45de32fd2b57
schedule: 30 15 * * 1-5  (交易日 15:30)
deliver: origin  (推送到聊天窗口)
```

### 输出示例

```
📊 个人回撤监控日报 — 2026-06-01

  📈 上证50ETF (510050)  现价: 2.9700
     📉 +¥20,000 — 建议加仓 ¥20,000

  📈 科创50ETF (588000)  现价: 1.7500
     📉 +¥10,000 — 建议加仓 ¥10,000
     📉 +¥20,000 — 建议加仓 ¥20,000
     ⚠️ 建议观望不加仓

  📈 芯片ETF (159995)  现价: 2.3570
     📉 +¥5,000 — 建议加仓 ¥5,000
     📉 +¥10,000 — 建议加仓 ¥10,000
     📉 +¥20,000 — 建议加仓 ¥20,000
     ⚠️ 建议观望不加仓
```

### 与通用回撤策略的区别

| 对比维度 | drawdown-rebalance（通用） | drawdown-personal（你专属） |
|----------|--------------------------|--------------------------|
| 触发方式 | 持仓百分比加仓 | 固定金额加仓 |
| 操作类型 | 加仓 + 减仓（反弹卖） | 仅加仓/观望 |
| 状态重置 | 不会自动重置 | 价格恢复峰值后自动重置 |
| 判断依据 | 当前回撤绝对值 | 回撤趋势变化（新发生 vs 历史） |
| 适用场景 | ETF定投管理 | 盯盘补仓提醒，不错过回调机会 |

### 个人策略常见陷阱

#### 1. 趋势判断 vs 绝对值判断（最重要！）
```python
# ❌ 错误：用当前回撤绝对值判断
if current_dd <= -5: signal(...)  # 会把AAPL(-55%)这种老回撤也触发

# ✅ 正确：比较回撤趋势变化
# last_dd = 上次扫描时的回撤值
# current_dd = 本次回撤值
if last_dd > thresh >= current_dd:  # 只触发新跨越的档位
    signal(...)
```
首次扫描时，会读取近 `trend_days`（默认10日）的回撤趋势作为起点，
`last_dd` 设为趋势起点的回撤值，只触发从起点到当前之间新跨越的档位。
这样老回撤（如AAPL的-55%）不会误报。

#### 2. 同一天多档位触发
```python
# ❌ 错误：用日期阻塞
if current_date == last_signal_date: continue  # 第一个触发后全堵住

# ✅ 正确：用 alerted set 逐档追踪
if idx in state["alerted"]: continue
state["alerted"].add(idx)  # 每个档位独立标记
```
阈值是扁平的 — 当回撤从-2%加深到-9%时，应同时触发-3%、-5%、-8%三个档位。

#### 3. 状态重置
- 状态存储在内存中，每次扫描时读取 re-evaluate
- 当回撤恢复至 `reset_at_pct`（默认-1%）时自动重置
- 重置后发一条「🔄 回撤已恢复」通知
- 重置后 `alerted` 清空，下一轮回撤从头触发

#### 4. 首次扫描初始化
- 首次扫描时，`last_dd` 设为 `trend_days` 前的回撤值
- 如果某个标的在 `trend_days` 内回撤从-2%跌到-9%
- 首次扫描会触发-3%、-5%、-8%三个档位（正确——这些是新发生的回撤）
- 之后每日扫描只检测当天的新变化

详细数据源参考见 `references/data-source-quirks.md`。

## 添加新策略（完整4步）

### 步骤1：在 `strategies/` 下新建 Python 文件

继承 `BaseStrategy`，实现 `evaluate()` 方法：

```python
# strategies/my_new_strategy.py
from .base import BaseStrategy, Signal

class MyNewStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my-strategy"

    @property
    def description(self) -> str:
        return "我的新策略"

    def evaluate(self, symbol, market, df, position=None):
        signals = []
        # ... 分析 df（date, open, close, high, low, volume）
        # ... 生成 Signal 列表
        signals.append(Signal(
            action="buy",           # buy/sell/add/reduce/hold/alert
            symbol=symbol,
            market=market,
            price=df["close"].values[-1],
            confidence=0.7,
            strategy=self.name,
            reason="策略触发原因描述",
        ))
        return signals
```

### 步骤2：在 `core/run.py` 的 `_load_strategy()` 中注册

```python
elif name == "my-strategy":
    from strategies.my_new_strategy import MyNewStrategy
    return MyNewStrategy(...)
```

### 步骤3：在 `config/strategies.yaml` 中添加配置

```yaml
- name: "my-strategy"
  enabled: true
  apply_to: "etf"     # all / etf / stock / fund
  params:
    param1: value1
```

### 步骤4：可选 — 在 `config/symbols.yaml` 中添加新标的

```yaml
- symbol: "159690"
  name: "有色ETF"
  market: a
  category: ETF
```

## 数据源

复用 global-market 已验证的数据源：

| 类型 | 数据源 | 函数 |
|------|--------|------|
| A股实时行情 | 腾讯 qt.gtimg.cn | `quote_a()` |
| 美股实时行情 | 腾讯 qt.gtimg.cn | `quote_us()` |
| 港股实时行情 | 新浪 hq.sinajs.cn | `quote_hk()` |
| 基金净值 | 天天基金 fundgz | `quote_fund()` |
| A股/港股历史K线 | Tencent ifzq | `_fetch_ifzq()` |
| 美股历史K线 | 新浪 US_MinKService | `_fetch_sina_us()` |
| 基金历史净值 | akshare | `_fetch_fund_nav()` |

## 常见的策略思路（供后续添加参考）

| 策略名 | 逻辑简述 |
|--------|----------|
| MACD金叉/背离 | MACD柱/DIF/DEA交叉 + 顶/底背离 |
| RSI超买超卖 | RSI(14)低于30买入，高于70卖出 |
| BOLL通道 | 突破上轨减仓，跌破下轨加仓 |
| 量价背离 | 价格新高但成交量萎缩 |
| 网格交易 | 设定价格网格，每格买卖固定份额 |
| 动量轮动 | 比较多个标的动量，切换最强品种 |
| 均线乖离 | 价格偏离MA一定百分比触发 |
| 布林带+RSI组合 | 多重信号过滤减小误判 |

## Common Pitfalls

1. **首次运行需要安装依赖**：`pip install pyyaml pandas numpy akshare matplotlib`
2. **A股代码 6 位纯数字**：基金（01/02开头）和 A 股代码共用`_resolve_a_code`，自动兜底
3. **akshare 基金净值首次调用延迟**：约2-3秒（pandas加载），后续调用快
4. **腾讯云环境注意限流**：`time.sleep(0.3)` 已内置，但批量调大仍可能被限
5. **data不足时策略自动静默跳过**：`min_data_days: 20` 可在 strategies.yaml 调整
6. **金叉/死叉有滞后性**：MA均线是滞后指标，建议结合成交量判断信号可靠性
7. **添加新策略后必须在 `_load_strategy()` 注册**：否则不生效
8. **持仓快照在每次 `--add-position` 或 `save_snapshot` 时追加**，不会覆盖历史
9. **symbols.yaml 中 market 必须正确**：错误的市场类型会导致数据获取失败，自动检测可能不准
10. **美股代码注意大小写**：A股大小写均可，美股建议全大写

### 数据源解析陷阱

这些陷阱在 global-market 的 `references/` 参考文档中有详细说明，但编写新脚本时极易踩到：

#### ifzq API（A股/港股历史K线）
- **JSON key 是 prefix+code**：如 `sh512890` 而非 `512890`。`d.get("data", {}).get(code)` 返回 None。必须用 `f"{prefix}{code}"` 构建 key。
- **qfqday 仅老股有**：次新 ETF 和港股只有 `day` 字段。必须降级获取：`records.get("qfqday") or records.get("day")`。

#### 新浪 US_MinKService（美股历史K线）
- **数据包裹在括号中**：`var data=([{...}])` 必须先 strip 外层括号 `(...)` 再 JSON 解析。
- **行格式是 dict**：每行是 `{"d":"date","o":"open","c":"close","h":"high","l":"low","v":"volume"}`，不是数组。按索引 `row[0]` 会报错。
- **海量历史数据**：AAPL 从 1984 年至今约 9958 条，务必控制 datalen 参数。

#### 回撤策略阈值排序
- **档位按回撤深度从浅到深定义**：如 `[(-5,10), (-10,15), (-15,25), (-20,40)]`
- **必须从最深档位开始匹配**：回撤 -26% 时应触发 (-20, 40) 而非 (-5, 10)
- 代码中必须 `sorted(thresholds, reverse=True)` + `break`，否则循环到浅档位覆盖深档位

详细数据源参考见 global-market 的 `references/ifzq-api.md` 和 `references/nasdaq-api.md`。

## Verification Checklist

- [ ] `python3 ~/.hermes/skills/fsi/price-monitor/core/run.py` 全量扫描无报错
- [ ] 回撤策略对 ETF 输出正确加仓/减仓信号
- [ ] 金叉死叉策略输出买卖信号
- [ ] 均线排列策略输出多头/空头判断
- [ ] `--portfolio` 正确显示当前持仓和盈亏
- [ ] `--add-position` 正确添加持仓并保存快照
- [ ] 持仓快照 JSON 可读、结构完整
- [ ] `quickstart.py` 演示流程完整无报错
- [ ] 各策略支持 `apply_to` 过滤（all/etf/stock/fund）
