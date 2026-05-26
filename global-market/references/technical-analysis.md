# 技术面量化分析脚本（金叉/死叉/MACD/支撑阻力）

## 概述

独立于 `run.py` 的量化分析工具。数据源直接调用 Tencent ifzq API 获取A股/港股K线历史数据（无需 akshare），通过 numpy 计算技术指标。

## 用法

```bash
~/venv/bin/python3 technical-analysis.py "002938"  # 鹏鼎控股
```

## 完整源码

```python
#!/usr/bin/env python3
"""个股技术面量化分析 — 金叉/死叉/MACD/支撑阻力/综合评分"""

import numpy as np
import requests as req
from datetime import datetime, timedelta


def fetch_a_stock_history(code, days=200):
    """从 Tencent ifzq API 获取A股前复权日线"""
    prefix = "sh" if code.startswith(("60", "68")) else "sz"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},qfq"
    resp = req.get(url, timeout=15)
    data = resp.json()
    try:
        records = data["data"][f"{prefix}{code}"]["qfqday"]
    except (KeyError, TypeError):
        try:
            records = data["data"][f"{prefix}{code}"]["day"]
        except (KeyError, TypeError):
            return None
    if not records:
        return None
    parsed = []
    for r in records:
        try:
            dt = datetime.strptime(r[0], "%Y-%m-%d")
            parsed.append({
                "date": dt, "open": float(r[1]), "close": float(r[2]),
                "high": float(r[3]), "low": float(r[4]),
                "volume": int(float(r[5])),
            })
        except (IndexError, ValueError, TypeError):
            continue
    return parsed if parsed else None


def fetch_hk_stock_history(code, days=200):
    """从 Tencent ifzq API 获取港股日线"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk{code},day,,,{days},qfq"
    resp = req.get(url, timeout=15)
    data = resp.json()
    try:
        records = data["data"][f"hk{code}"]["day"]
    except (KeyError, TypeError):
        return None
    if not records:
        return None
    parsed = []
    for r in records:
        try:
            dt = datetime.strptime(r[0], "%Y-%m-%d")
            parsed.append({
                "date": dt, "open": float(r[1]), "close": float(r[2]),
                "high": float(r[3]), "low": float(r[4]),
                "volume": int(float(r[5])),
            })
        except (IndexError, ValueError, TypeError):
            continue
    return parsed if parsed else None


def fetch_us_stock_history(symbol, days=200):
    """从新浪美股 API 获取美股日线"""
    url = ("https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
           f"var%20data=/US_MinKService.getDailyK?symbol=.{symbol}&datalen={days}")
    headers = {"Referer": "https://finance.sina.com.cn"}
    resp = req.get(url, headers=headers, timeout=15)
    raw = resp.text.strip()
    import re, json
    m = re.search(r"\[.+?\]", raw, re.DOTALL)
    if not m:
        return None
    records = json.loads(m.group())
    parsed = []
    for r in records:
        try:
            parsed.append({
                "date": datetime.strptime(r["d"], "%Y-%m-%d"),
                "open": float(r["o"]), "close": float(r["c"]),
                "high": float(r["h"]), "low": float(r["l"]),
                "volume": int(float(r.get("v", 0))),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return parsed if parsed else None


def calc_ma(data, period):
    """计算移动平均线"""
    if len(data) < period:
        return None
    return np.convolve(data, np.ones(period) / period, mode="valid")


def calc_ema(data, period):
    """计算指数移动平均线"""
    result = [data[0]]
    for v in data[1:]:
        result.append(result[-1] * (period - 1) / (period + 1) + v * 2 / (period + 1))
    return np.array(result)


def analyze_stock(code, market="a"):
    """主分析函数"""

    # 1. 获取数据
    if market == "a":
        hist = fetch_a_stock_history(code, 200)
    elif market == "hk":
        hist = fetch_hk_stock_history(code, 200)
    elif market == "us":
        hist = fetch_us_stock_history(code, 200)
    else:
        return "❌ 不支持的市场类型"

    if not hist or len(hist) < 20:
        return f"❌ 数据不足（当前{len(hist) if hist else 0}条，需≥20条）"

    hist.sort(key=lambda x: x["date"])
    closes = np.array([d["close"] for d in hist])
    dates = [d["date"] for d in hist]
    highs = np.array([d["high"] for d in hist])
    lows = np.array([d["low"] for d in hist])
    volumes = np.array([d.get("volume", 0) for d in hist])

    lines = []
    sep = "=" * 68
    lines.append(sep)
    lines.append(f"  {code} — 技术面量化分析（{len(dates)}个交易日）")
    lines.append(f"  当前价: {closes[-1]:.2f}")
    lines.append(sep)

    # 2. 均线排列
    ma_periods = [5, 10, 20, 30, 60, 90, 120]
    mas = {}
    for p in ma_periods:
        m = calc_ma(closes, p)
        if m is not None:
            mas[p] = m

    lines.append("\n📊 均线排列：")
    curr = {p: mas[p][-1] for p in sorted(mas.keys())}
    sorted_ma = sorted(curr.items(), key=lambda x: x[1], reverse=True)
    order = " > ".join([f"MA{p}({v:.2f})" for p, v in sorted_ma])
    lines.append(f"  {order}")
    is_bull = all(sorted_ma[i][1] >= sorted_ma[i+1][1] for i in range(len(sorted_ma)-1))
    lines.append(f"  {'✅ 标准多头排列' if is_bull else '⚠️ 非标准排列'}")

    # 3. 金叉/死叉检测
    lines.append("\n🔀 金叉/死叉（近90日）：")
    pairs = [("MA5-MA20", 5, 20), ("MA10-MA30", 10, 30),
             ("MA20-MA60", 20, 60), ("MA30-MA90", 30, 90),
             ("MA60-MA120", 60, 120)]
    cutoff = dates[-1] - timedelta(days=90)
    bull_signals = 0
    bear_signals = 0

    for label, sp, lp in pairs:
        if sp not in mas or lp not in mas:
            continue
        m1, m2 = mas[sp], mas[lp]
        min_len = min(len(m1), len(m2))
        m1_t, m2_t = m1[-min_len:], m2[-min_len:]
        gold, death = [], []
        for i in range(1, min_len):
            idx = len(dates) - min_len + i
            if idx >= len(dates):
                continue
            if m1_t[i-1] <= m2_t[i-1] and m1_t[i] > m2_t[i]:
                if dates[idx] >= cutoff:
                    gold.append(dates[idx].strftime("%m/%d"))
            elif m1_t[i-1] >= m2_t[i-1] and m1_t[i] < m2_t[i]:
                if dates[idx] >= cutoff:
                    death.append(dates[idx].strftime("%m/%d"))
        status = "📈 多头(金叉)" if m1[-1] > m2[-1] else "📉 空头(死叉)"
        if m1[-1] > m2[-1]:
            bull_signals += 1
        else:
            bear_signals += 1
        parts = [f"  {label} → {status}"]
        if gold:
            parts.append(f"    金叉: {', '.join(gold)}")
        if death:
            parts.append(f"    死叉: {', '.join(death)}")
        lines.extend(parts)

    # 4. MACD
    lines.append("\n🔮 MACD：")
    dif_series = []
    ema12_v, ema26_v = closes[0], closes[0]
    for c in closes:
        ema12_v = ema12_v * 11/13 + c * 2/13
        ema26_v = ema26_v * 25/27 + c * 2/27
        dif_series.append(ema12_v - ema26_v)
    dea_series = calc_ema(np.array(dif_series), 9)
    macd = 2 * (dif_series[-1] - dea_series[-1])
    lines.append(f"  DIF: {dif_series[-1]:.2f}  DEA: {dea_series[-1]:.2f}  MACD柱: {macd:.2f}")
    if dif_series[-1] > dea_series[-1] and dif_series[-1] > 0:
        lines.append("  ✅ DIF在DEA上方 — MACD多头，动能向上")
    elif dif_series[-1] < dea_series[-1]:
        lines.append("  ❌ DIF在DEA下方 — MACD空头")
    else:
        lines.append("  ⚠️ DIF为正但贴近DEA — 中性")

    # 5. 支撑/阻力
    lines.append("\n🎯 关键价位（60日）：")
    rc, rh, rl = closes[-60:], highs[-60:], lows[-60:]
    r2, r1 = np.percentile(rh, 85), np.percentile(rh, 70)
    s1, s2 = np.percentile(rl, 30), np.percentile(rl, 15)
    lines.append(f"  🔴 R2: {r2:.2f}  🟠 R1: {r1:.2f}")
    lines.append(f"  🟢 S1: {s1:.2f}  🔵 S2: {s2:.2f}")

    # 6. 量能
    lines.append("\n📈 量能：")
    v20 = np.mean(volumes[-20:])
    tv = volumes[-1]
    lines.append(f"  今日: {tv/1e4:.0f}万手 | 20日均: {v20/1e4:.0f}万手 | 量比: {tv/v20:.2f}x")
    if tv > v20 * 2:
        lines.append("  🚀 倍量！主力大幅介入")
    elif tv > v20 * 1.5:
        lines.append("  🔥 显著放量")

    # 7. 短期动量
    lines.append("\n📊 短期动量：")
    if len(closes) >= 21:
        lines.append(f"  近20日: {(closes[-1]/closes[-21]-1)*100:+.2f}%")
    if len(closes) >= 6:
        lines.append(f"  近5日: {(closes[-1]/closes[-6]-1)*100:+.2f}%")
    up_d = sum(1 for i in range(1, min(21, len(closes))) if closes[-i] > closes[-i-1])
    dn_d = min(20, len(closes)-1) - up_d
    lines.append(f"  涨跌比: {up_d}涨/{dn_d}跌（{up_d/max(1,up_d+dn_d)*100:.0f}%）")

    # 8. 综合评分
    lines.append(f"\n{sep}")
    lines.append("  📋 量化策略评分")
    lines.append(sep)
    ma20_val = mas[20][-1] if 20 in mas else closes[-1]
    bias = (closes[-1] / ma20_val - 1) * 100
    lines.append(f"\n  MA20偏离: {bias:+.2f}%{' ⚠️ 超买' if abs(bias) > 8 else ''}")

    score = 0
    score += 1 if is_bull else -1
    score += 1 if abs(bias) < 8 else 0
    score += 1 if dif_series[-1] > dea_series[-1] else -1
    score += 1 if tv > v20 else 0
    score += 1 if bull_signals > bear_signals else -1

    verdict_map = {5: "强烈看多 🔥📈", 4: "看多 📈", 3: "偏多 ➡️📈",
                   2: "中性偏多 ➡️", 1: "中性 ➡️", 0: "中性 ➡️",
                   -1: "中性偏弱 ➡️📉", -2: "偏空 📉",
                   -3: "看空 📉📉", -4: "强烈看空 🔥📉", -5: "强烈看空 🔥📉"}
    verdict = verdict_map.get(max(min(score, 5), -5), "中性 ➡️")
    lines.append(f"\n  综合评分: {score}/5 → {verdict}")

    # 关键观察
    lines.append(f"\n  【下周关键观察】")
    if 5 in mas: lines.append(f"  1. 短线支撑: MA5({mas[5][-1]:.2f}) → MA10({mas[10][-1]:.2f})" if 10 in mas else "")
    if 20 in mas: lines.append(f"  2. 中期生命线: MA20({mas[20][-1]:.2f})")
    lines.append(f"  3. 上方阻力: {r2:.2f}附近")
    if bull_signals > bear_signals:
        lines.append(f"  4. 金叉共振: {bull_signals}/{len(pairs)}对均线多头 ✅")
    if abs(bias) > 8:
        lines.append(f"  5. ⚠️ 偏离度过大，注意回调风险")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "002938"
    market = sys.argv[2] if len(sys.argv) > 2 else "a"
    result = analyze_stock(code, market)
    print(result)
```
