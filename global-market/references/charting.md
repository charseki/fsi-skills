# K线走势图生成（matplotlib）

## 前置条件

```bash
~/venv/bin/pip install matplotlib numpy
# 中文字体（WenQuanYi Zen Hei）
sudo apt install fonts-wqy-zenhei
```

使用 `~/venv/bin/python3` 而非系统 Python。

## 自动生成（推荐）

脚本 `scripts/run.py` 内置两种图表模式。

### 方式一：指数K线图（`--history --chart`）

```bash
~/venv/bin/python3 run.py --history SPX --chart
~/venv/bin/python3 run.py --history NDX --chart
~/venv/bin/python3 run.py --history DJI --chart
~/venv/bin/python3 run.py --history COMP --chart
```

输出路径：`charts/` 目录，按参数动态命名：`NDX_history.png`（~132KB, 150dpi）。

### 方式二：个股K线趋势图（`--chart` / 动态参数）

支持两种用法，K线天数和均线列表灵活自定义，输出文件自动按参数命名：

```bash
# --chart 标志（默认90日 + MA20/MA90）
~/venv/bin/python3 run.py 600519 --chart        # 输出: 600519_K90_MA20_MA90.png
~/venv/bin/python3 run.py AAPL --chart          # 输出: AAPL_K90_MA20_MA90.png

# 动态参数（自定义天数 + 自定义均线，无需 --chart）
# 格式: <股票>,K<天数>,[MA<周期1>,MA<周期2>,...]
~/venv/bin/python3 run.py "002938,K120,[MA20,MA45,MA120]"   # 输出: 002938_K120_MA20_MA45_MA120.png
~/venv/bin/python3 run.py "茅台,K60,[MA10,MA20]"            # 输出: 600519_K60_MA10_MA20.png
~/venv/bin/python3 run.py "AAPL,[MA50,MA100,MA200]"         # 输出: AAPL_K90_MA50_MA100_MA200.png
```

## K线颜色惯例

脚本根据市场类型自动切换颜色方案：

| 市场 | 上涨(阳线) | 下跌(阴线) | 惯例 |
|------|-----------|-----------|------|
| A 股 / 港股 | 🔴 `#ff4466` 红 | 🟢 `#00ff88` 绿 | 亚洲惯例 |
| 美股 / 欧美 | 🟢 `#00ff88` 绿 | 🔴 `#ff4466` 红 | 欧美惯例 |

实现方式：在 `generate_stock_chart()` 中根据 `market_type` 设置 `UP_COLOR` / `DOWN_COLOR` 变量，K线实体、影线、成交量柱统一使用这对变量。

## A股成交量换算

A 股 ifzq API 返回的 volume 单位为 **手**（1手=100股）。`generate_stock_chart()` 自动换算为成交额（百万元）：

```python
if market_type == "a":
    # 手数 × 收盘价 / 10000 = 成交额(百万元)
    volumes = vol_raw * closes / 10000.0
    VOL_LABEL = "成交额(百万元)"
```

其中 `closes` 为当日收盘价数组，与 `vol_raw` 一一对应逐日换算。

## 均线计算的数据策略

为确保长周期均线（如 MA120）在展示周期仅为 120 日时仍能完整显示，`generate_stock_chart()` 不再截取数据：

```python
# ❌ 旧做法：截取后只剩 k_period 条，MA120 只有最后一个点可见
# parsed = parsed[-k_period:]

# ✅ 新做法：保留全部数据用于均线计算，用 xlim 限定展示范围
# （parsed 未截取，包含 240+ 条历史数据）
# ... 均线计算使用全量 closes 数组 ...
# 绘图完成后：
if len(dates) > k_period:
    ax1.set_xlim(dates[-k_period], dates[-1])
    ax2.set_xlim(dates[-k_period], dates[-1])
```

这样 MA120 从第 119 条数据开始绘制，在 x 轴限定范围内完整可见。

## 动态文件名生成

```python
ma_part = "_".join([f"MA{p}" for p in ma_periods])     # "MA20_MA45_MA120"
code_safe = re.sub(r"[^A-Za-z0-9]", "", code)          # 过滤中文/特殊字符
filename = f"{code_safe}_K{k_period}_{ma_part}.png"    # "002938_K120_MA20_MA45_MA120.png"
out_path = os.path.join(_CHARTS_DIR, filename)
```

对于 A 股名称搜索，`main()` 中通过 `_resolve_a_code()` 将名称转为 6 位代码后再传给图表函数，确保文件名使用数字代码而非中文名。

## 数据源

### A股历史K线 — Tencent ifzq API

```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},qfq
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `sh{code}` / `sz{code}` | 前缀 + 6位代码 | `sh600519`, `sz002938` |
| `qfqday` | 前复权日线（推荐） | — |
| `day` | 日线（非复权） | — |

返回格式：

```json
{
  "data": {
    "sh600519": {
      "qfqday": [
        ["2026-01-05", "1385.000", "1426.000", "1431.880", "1385.000", "70949.000"]
        //   date       open       close      high        low       volume
      ]
    }
  }
}
```

注意：`qfqday` 索引排列为 **date, open, close, high, low, volume**。`close` 在索引 2，不是索引 1。

### 港股历史K线 — Tencent ifzq API

同上，前缀 `hk{code}`，数据在 `day` 字段（无前复权）：

```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk00700,day,,,120,qfq
```

### 美股历史K线 — Sina US_MinKService API

```
GET https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_MinKService.getDailyK?symbol={symbol}&datalen={datalen}
```

需要 `Referer: https://finance.sina.com.cn` header。

| 股类型 | symbol | 示例 |
|--------|--------|------|
| 个股 | 直接使用ticker | `AAPL`, `TSLA`, `GOOGL` |
| 指数 | `.{code}` | `.INX`(SPX), `.DJI`, `.NDX`, `.IXIC`(COMP) |

返回格式：`var data=([{"d":"2026-01-05","o":"306.12","h":"311.40","l":"305.84","c":"308.82","v":"43670223"},...])`

注意事项：
- 数据从 1984 年至今
- 响应开头可能有 `/*<script>location.href='//sina.com';</script>*/` 注释，用 `re.search(r"\[.+\]", raw, re.DOTALL)` 提取即可

## 手动生成流程

### 1. 获取数据

```python
import requests, json, re
from datetime import datetime

# A股示例：Tencent ifzq
resp = requests.get(
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    "?param=sz002938,day,,,150,qfq",
    timeout=15
)
data = resp.json()
records = data["data"]["sz002938"]["qfqday"]
# [date, open, close, high, low, volume]

# 美股示例：Sina US API
headers = {"Referer": "https://finance.sina.com.cn"}
resp = requests.get(
    "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
    "var%20data=/US_MinKService.getDailyK"
    "?symbol=AAPL&datalen=120",
    headers=headers, timeout=15
)
raw = resp.text.strip()
match = re.search(r"\[.+\]", raw, re.DOTALL)
records = json.loads(match.group())
# [{"d":date, "o":open, "h":high, "l":low, "c":close, "v":volume}, ...]
```

### 2. 统一数据格式

两种数据源统一为 list[dict] 格式：

```python
parsed = []
for r in records:
    if isinstance(r, list):  # Tencent ifzq 格式
        parsed.append({
            "date": datetime.strptime(r[0], "%Y-%m-%d"),
            "open": float(r[1]),
            "close": float(r[2]),
            "high": float(r[3]),
            "low": float(r[4]),
            "volume": int(float(r[5])),
        })
    else:  # Sina US 格式
        parsed.append({
            "date": datetime.strptime(r["d"], "%Y-%m-%d"),
            "open": float(r["o"]),
            "close": float(r["c"]),
            "high": float(r["h"]),
            "low": float(r["l"]),
            "volume": int(r.get("v", 0)),
        })
```

### 3. 生成K线图（个股）

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.patches import Rectangle

# 中文字体
fm.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False

# 排序（保留全部历史数据用于均线计算，画图时用 xlim 限定展示范围）
parsed.sort(key=lambda x: x["date"])

dates = [d["date"] for d in parsed]
opens = np.array([d["open"] for d in parsed])
highs = np.array([d["high"] for d in parsed])
lows = np.array([d["low"] for d in parsed])
closes = np.array([d["close"] for d in parsed])
volumes = np.array([d.get("volume", 0) for d in parsed])

plt.style.use("dark_background")
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(14, 9),
    gridspec_kw={"height_ratios": [3, 1]}, sharex=True,
)
fig.patch.set_facecolor("#1a1a2e")

# K线颜色惯例：亚洲红涨绿跌 / 欧美绿涨红跌
if market_type in ("a", "hk"):
    UP_COLOR = "#ff4466"    # 红 = 阳线(上涨)
    DOWN_COLOR = "#00ff88"  # 绿 = 阴线(下跌)
else:
    UP_COLOR = "#00ff88"    # 绿 = 上涨
    DOWN_COLOR = "#ff4466"  # 红 = 下跌

# K线绘制
x_dates = mdates.date2num(dates)
candle_w = (x_dates[1] - x_dates[0]) * 0.7 if len(dates) > 1 else 0.6

for i in range(len(dates)):
    x = x_dates[i]
    o, h, l, c = opens[i], highs[i], lows[i], closes[i]
    up = c >= o
    color = UP_COLOR if up else DOWN_COLOR
    ax1.plot([x, x], [l, h], color=color, linewidth=0.7, alpha=0.5)
    rect = Rectangle(
        (x - candle_w/2, min(o, c)), candle_w, abs(c - o) or 0.005,
        facecolor=color, edgecolor=color, alpha=0.85, linewidth=0.5,
    )
    ax1.add_patch(rect)

# 动态均线（MA20, MA45, MA120 ...）
MA_COLORS = ["#ffcc00", "#ff6bff", "#00d4ff", "#ff6b35",
             "#88ff88", "#ff4466", "#00ffff", "#ffffff"]
for i, period in enumerate(ma_periods):
    if len(closes) >= period:
        ma = np.convolve(closes, np.ones(period)/period, mode="valid")
        ax1.plot(dates[period-1:], ma, color=MA_COLORS[i % len(MA_COLORS)],
                linewidth=1.6, linestyle="--", alpha=0.7, label=f"MA{period}")

# 标注、标题等...（详见 scripts/run.py generate_stock_chart）
```

## 中文字体配置

服务器 DejaVu Sans 不含 CJK 字形（会报 `Glyph ... missing from font` 警告）。

**修复方式**：

```python
import matplotlib.font_manager as fm
fm.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
```

字体路径：`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`（Ubuntu `apt install fonts-wqy-zenhei`）。

## 动态参数格式说明

`parse_chart_params()` 支持两种输入格式：

```
"股票查询,K<天数>,[MA<周期1>,MA<周期2>,...]"
```

正则解析流程：
1. 先 `re.search(r"\[([^\]]*?MA\d+[^\]]*?)\]", query)` 提取均线列表
2. 在剩余字符串中 `re.search(r"K(\d+)", remaining)` 提取K线天数
3. 剩余部分作为股票查询

均线配色：8色循环（黄/紫/青/橙/绿/红/青/白），每条线 `linestyle="--"`。

## 注意事项

- **个股查询的 --chart 和动态参数互斥**，动态参数优先
- **均线周期大于数据长度**时自动跳过该均线，不报错
- **数据请求量**：`max(120, k_period * 2)` 个日历日，确保覆盖指定交易日数
- **K线周期不足**指定值时，用实际可用天数展示
- **图表保存路径**：按参数动态命名于 `charts/` 目录，个股如 `002938_K120_MA20_MA45_MA120.png`，指数如 `NDX_history.png`
- **Tencent ifzq API 前复权数据**（qfqday）当日可能延迟，收盘后更新
- **Sina US API** 个股数据从1984年起，指数从2004年起，请求 `datalen=120` 即可获取约90个交易日
