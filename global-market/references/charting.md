# 行情走势图生成 (matplotlib)

## 前置条件

matplotlib + numpy 已安装在 `~/venv/`：

```bash
~/venv/bin/pip install matplotlib numpy
```

使用 `~/venv/bin/python3` 而非系统 Python（系统 Python 因 PEP 668 拒绝安装第三方包）。

## 自动生成（推荐）

脚本 `scripts/run.py` 已内置 `--chart` 模式，一键出图：

```bash
~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history SPX --chart
~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history NDX --chart
~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history DJI --chart
~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history COMP --chart
```

输出路径：`/tmp/hermes_index_chart.png`（150dpi, ~132KB）。

## 手动生成流程

### 1. 获取历史数据

使用新浪美股 API（不受腾讯云限制，无需 API key，支持全部4个指数）：

```python
import requests, json, re
from datetime import datetime

url = (
    "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
    "var%20data=/US_MinKService.getDailyK"
    "?symbol=.INX&datalen=60"
)
headers = {'Referer': 'https://finance.sina.com.cn'}
resp = requests.get(url, headers=headers, timeout=15)
raw = resp.text.strip()

# 提取 JSON 数组
match = re.search(r'\[.+\]', raw, re.DOTALL)
records = json.loads(match.group())

# 解析：
dates = [datetime.strptime(r['d'], '%Y-%m-%d') for r in records]
closes = [float(r['c']) for r in records]
opens  = [float(r['o']) for r in records]
highs  = [float(r['h']) for r in records]
lows   = [float(r['l']) for r in records]
```

### 2. 生成图表

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                               gridspec_kw={'height_ratios': [3, 1]},
                               sharex=True)

# 上方：收盘价线 + 均线
ax1.fill_between(dates, closes, min(closes)*0.95, alpha=0.12, color='#00d4ff')
ax1.plot(dates, closes, color='#00d4ff', linewidth=2.5, label='Close', zorder=3)

# 5日均线
if len(closes) >= 5:
    ma5 = np.convolve(closes, np.ones(5)/5, mode='valid')
    ax1.plot(dates[4:], ma5, color='#ff6b35', linewidth=1.5,
             linestyle='--', alpha=0.8, label='5-Day MA', zorder=2)

# 20日均线
if len(closes) >= 20:
    ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
    ax1.plot(dates[19:], ma20, color='#ffcc00', linewidth=1.2,
             linestyle='--', alpha=0.6, label='20-Day MA', zorder=2)

# 标注最高/最低点
max_i, min_i = np.argmax(closes), np.argmin(closes)
ax1.scatter(dates[max_i], closes[max_i], color='#00ff88', s=140, zorder=5, marker='^')
ax1.scatter(dates[min_i], closes[min_i], color='#ff4466', s=140, zorder=5, marker='v')
ax1.annotate(f'High ${closes[max_i]:,.0f}', (dates[max_i], closes[max_i]),
           textcoords="offset points", xytext=(15, 15),
           fontsize=10, color='#00ff88', fontweight='bold')
ax1.annotate(f'Low ${closes[min_i]:,.0f}', (dates[min_i], closes[min_i]),
           textcoords="offset points", xytext=(15, -20),
           fontsize=10, color='#ff4466', fontweight='bold')

# 当前价格参考线
pct = (closes[-1] - closes[0]) / closes[0] * 100
ax1.axhline(y=closes[-1], color='#ffaa00', linewidth=1, linestyle=':', alpha=0.5)
ax1.annotate(f'Latest ${closes[-1]:,.0f} ({pct:+.1f}%)',
           (dates[-1], closes[-1]), textcoords="offset points",
           xytext=(10, 5), fontsize=11, color='#ffaa00', fontweight='bold')

ax1.set_ylabel('Price (USD)', fontsize=12, color='#ccc')
ax1.set_title(f'{name} ({symbol}) — {dates[0].strftime("%m/%d")} ~ {dates[-1].strftime("%m/%d")}',
             fontsize=18, fontweight='bold', color='white', pad=20)
ax1.legend(fontsize=11, loc='upper left')
ax1.grid(True, alpha=0.12, linestyle='--')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# 下方：成交量
volumes = [int(r.get('v') or 0) for r in records]
if any(volumes):
    colors_vol = ['#00ff88' if c >= o else '#ff4466'
                  for c, o in zip(closes, opens)]
    ax2.bar(dates, volumes, color=colors_vol, alpha=0.5, width=0.8)
    ax2.set_ylabel('Volume', fontsize=11, color='#ccc')
    ax2.grid(True, alpha=0.08, linestyle='--')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
fig.autofmt_xdate()
plt.tight_layout()

plt.savefig('/tmp/hermes_index_chart.png', dpi=150,
            bbox_inches='tight', facecolor='#1a1a2e')
```

## 注意事项

- **标题避免中文**：服务器 DejaVu Sans 字体不支持 CJK 字符，无法渲染中文。用英文标题 + 微信文字补充说明
- **matplotlib 需安装在 venv**：`~/venv/bin/pip install matplotlib numpy`
- **支持的指数**：NDX, SPX, DJI, COMP（全部通过新浪美股 API）
- **数据周期**：`datalen=60` 够一个月交易日，实际约 30-42 条
- **图表保存路径**：统一用 `/tmp/hermes_index_chart.png` 避免权限问题
