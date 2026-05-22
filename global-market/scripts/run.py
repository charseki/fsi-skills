#!/usr/bin/env python3
"""全球市场速查 Skill — 自动识别市场并路由到对应数据源"""

import sys
import re
import json
import requests as req
from datetime import datetime, timedelta

# =========================================================
# 数据源
#   A股/美股: 腾讯行情 qt.gtimg.cn
#   港股:     新浪行情 hq.sinajs.cn (需 Referer)
#   名称搜索: 新浪建议 suggest3.sinajs.cn
#   基金:     天天基金 fundgz.1234567.com.cn
#   外汇:     open.er-api.com (免费，无需 API key)
#   指数历史: Nasdaq 官方 API api.nasdaq.com
# =========================================================

SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}
NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nasdaq.com/",
}

# 全局 Session（复用连接，降低延迟）
_HTTP = req.Session()


# ═════════════════════════════════════════════════════════
# 市场检测
# ═════════════════════════════════════════════════════════

def detect_market(query):
    """根据输入自动判断市场类型；返回 (market_type, identifier)"""
    q = query.upper().strip()

    # --- 外汇检测（优先级最高）---
    fx_keywords = ["汇率", "美元", "欧元", "日元", "英镑", "港币", "人民币",
                   "加元", "澳元", "韩元", "卢布", "卢比",
                   "USD", "CNY", "EUR", "JPY", "GBP", "HKD", "CAD", "AUD"]
    for kw in fx_keywords:
        if kw in query or kw in q:
            return "fx", query

    # --- 港股检测（5位数字 .HK 或不带）---
    if q.endswith(".HK"):
        return "hk", q.replace(".HK", "").zfill(5)
    if q.isdigit() and len(q) == 5:
        return "hk", q.zfill(5)

    # --- 美股检测（1-5位纯字母）---
    if re.match(r"^[A-Z]{1,5}$", q) and q not in {"SH", "SZ", "HSI"}:
        return "us", q

    # --- 默认为 A 股 ---
    return "a", query


# ═════════════════════════════════════════════════════════
# A股
# ═════════════════════════════════════════════════════════

def query_a_stock(query):
    """查询 A 股行情"""
    # 6 位数字 → 直接查 sh/sz
    if re.match(r"^\d{6}$", query):
        for prefix in ("sh", "sz"):
            parts = _tx_fetch(f"{prefix}{query}")
            if parts:
                return _format_a_stock(parts)
        # 6 位数字 A 股没查到 → 可能是个基金代码
        result_fund = query_fund(query)
        if result_fund:
            return result_fund
        return f"❌ A股/基金未找到「{query}」"

    # 非数字 → 名称搜索
    return search_a_by_name(query)


def search_a_by_name(query):
    """通过新浪建议接口按名称搜索 A 股"""
    try:
        url = f"https://suggest3.sinajs.cn/suggest/?key={query}&type=11,12&count=5"
        resp = _HTTP.get(url, headers=SINA_HEADERS, timeout=10)
        raw = resp.text.strip()

        if "suggestvalue=" not in raw:
            return f"❌ A股未找到「{query}」"

        data = raw.split('"')[1]
        if not data or data == ";":
            return f"❌ A股未找到「{query}」"

        # 取第一条匹配结果
        items = data.strip(";").split(";")
        for item in items:
            parts = item.split(",")
            if len(parts) >= 3:
                name = parts[0]
                market_flag = parts[1]
                code = parts[2]
                prefix = "sh" if market_flag == "11" else "sz" if market_flag == "12" else market_flag
                tx_code = f"{prefix}{code}"
                tx_parts = _tx_fetch(tx_code)
                if tx_parts:
                    return _format_a_stock(tx_parts)
        return f"❌ A股未找到「{query}」"
    except Exception:
        return f"❌ A股未找到「{query}」"


def _tx_fetch(code_str):
    """从腾讯行情获取数据，成功返回 parts list，失败返回 None"""
    try:
        url = f"https://qt.gtimg.cn/q={code_str}"
        resp = _HTTP.get(url, timeout=10)
        text = resp.text.strip()
        if "v_pv_none_match" in text:
            return None
        if not text.startswith("v_"):
            return None
        parts = text.split("~")
        if len(parts) < 35:
            return None
        if "none" in parts[1].lower():
            return None
        return parts
    except Exception:
        return None


def _format_a_stock(parts):
    """格式化 A 股行情输出"""
    name = parts[1]
    code = parts[2]
    price = parts[3]
    change = parts[31]
    change_pct = parts[32]
    high = parts[33]
    low = parts[34]
    open_p = parts[5]
    volume_hands = parts[6]  # 手

    cs = "📈" if float(change) > 0 else "📉" if float(change) < 0 else "➡️"

    # 成交额从组合字段解析：1323.00/49661/6594983723 → 第三段是成交额(元)
    amount_yi = "N/A"
    amount_raw = parts[35] if len(parts) > 35 else "0"
    if "/" in amount_raw:
        ap = amount_raw.split("/")
        if len(ap) >= 3 and ap[2]:
            try:
                amount_yi = f"{float(ap[2]) / 1e8:.2f}"
            except ValueError:
                pass

    volume_fmt = f"{int(float(volume_hands)):,}" if volume_hands else "N/A"

    return (
        f"{cs} **{name}**（{code}）\n"
        f"最新价: ¥{price}  涨跌幅: {change_pct}%\n"
        f"今开: ¥{open_p}  最高: ¥{high}  最低: ¥{low}\n"
        f"成交量: {volume_fmt}手  成交额: {amount_yi}亿"
    )


# ═════════════════════════════════════════════════════════
# 基金（天天基金 API 兜底）
# ═════════════════════════════════════════════════════════

def query_fund(code):
    """查询基金净值 — 天天基金 API；失败返回 None"""
    try:
        url = f"https://fundgz.1234567.com.cn/js/{code}.js"
        resp = _HTTP.get(url, timeout=10)
        raw = resp.text.strip()

        # JSONP 格式: jsonpgz({...})
        m = re.search(r"jsonpgz\((.+?)\)\s*;?\s*$", raw)
        if not m:
            return None

        data = json.loads(m.group(1))
        name = data.get("name", "未知")
        dwjz = data.get("dwjz", "--")    # 单位净值
        gsz = data.get("gsz", "--")       # 估算净值
        gszzl = data.get("gszzl", "--")   # 估算涨跌幅
        gztime = data.get("gztime", "")
        jzrq = data.get("jzrq", "")

        cs = "📈" if float(gszzl) > 0 else "📉" if float(gszzl) < 0 else "➡️" if gszzl != "--" else ""

        lines = [
            f"{cs} **{name}**（{code}）",
            f"估算净值: ¥{gsz}  估算涨跌幅: {gszzl}%",
            f"最新公布净值: ¥{dwjz}（{jzrq}）",
            f"估算时间: {gztime}",
        ]
        return "\n".join(lines)
    except Exception:
        return None


# ═════════════════════════════════════════════════════════
# 美股
# ═════════════════════════════════════════════════════════

def query_us_stock(symbol):
    """查询美股行情 — 腾讯行情接口"""
    try:
        sym = symbol.upper()

        # 指数代码符号映射（腾讯内部编码不同）
        INDEX_TX_MAP = {
            "SPX": "usINX",    # S&P 500 → .INX
            "DJI": "us.DJI",   # Dow Jones → .DJI
        }

        # 先尝试直接查询
        parts = _tx_fetch(f"us{sym}")
        # 如果没找到且是指数，尝试映射后的符号
        if not parts and sym in INDEX_TX_MAP:
            parts = _tx_fetch(INDEX_TX_MAP[sym])
        if not parts:
            return f"❌ 美股未找到「{symbol}」"

        cn_name = parts[1]
        code_display = parts[2]
        price = parts[3]
        change = parts[31]
        change_pct = parts[32]
        high = parts[33]
        low = parts[34]
        currency = parts[35] if len(parts) > 35 and parts[35] else "USD"
        open_p = parts[5]
        prev_close = parts[4]

        pe = parts[39] if len(parts) > 39 else ""
        en_name = parts[46] if len(parts) > 46 else ""
        week52_high = parts[48] if len(parts) > 48 else ""
        week52_low = parts[49] if len(parts) > 49 else ""

        display_name = en_name if en_name else cn_name
        cs = "📈" if float(change) > 0 else "📉" if float(change) < 0 else "➡️"

        lines = [
            f"{cs} **{display_name}**（{symbol.upper()}）",
            f"最新价: {currency}${price}  涨跌幅: {change_pct}%",
            f"今开: {open_p}  昨收: {prev_close}  最高: {high}  最低: {low}",
        ]
        if pe:
            lines.append(f"PE(TTM): {pe}")
        if week52_high:
            lines.append(f"52周范围: ${week52_low} - ${week52_high}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ 美股查询失败: {str(e)}"


# ═════════════════════════════════════════════════════════
# 港股
# ═════════════════════════════════════════════════════════

def query_hk_stock(code):
    """查询港股行情 — 新浪接口"""
    try:
        url = f"https://hq.sinajs.cn/list=hk{code}"
        resp = _HTTP.get(url, headers=SINA_HEADERS, timeout=10)
        raw = resp.text.strip()

        if "FAILED" in raw.upper():
            return f"❌ 港股未找到「{code}」"

        match = re.search(r'"(.+)"', raw)
        if not match:
            return f"❌ 港股解析失败: {code}"

        fields = match.group(1).split(",")
        if len(fields) < 10:
            return f"❌ 港股数据异常: {code}"

        en_name = fields[0]
        cn_name = fields[1]
        price = fields[2]
        prev_close = fields[3]
        high = fields[4]
        low = fields[5]
        open_p = fields[6]
        change = fields[7]
        change_pct = fields[8]
        turnover = fields[11] if len(fields) > 11 else "0"
        volume = fields[12] if len(fields) > 12 else "0"

        display_name = f"{cn_name}（{en_name}）" if en_name else cn_name
        cs = "📈" if float(change) > 0 else "📉" if float(change) < 0 else "➡️"

        turnover_yi = f"{float(turnover)/1e8:.2f}亿" if turnover and float(turnover) > 0 else "N/A"
        volume_yi = f"{float(volume)/1e8:.2f}亿" if volume and float(volume) > 0 else "N/A"

        return (
            f"{cs} **{display_name}**（{code}.HK）\n"
            f"最新价: HK${price}  涨跌幅: {change_pct}%\n"
            f"今开: HK${open_p}  最高: HK${high}  最低: HK${low}\n"
            f"成交量: {volume_yi}股  成交额: {turnover_yi}"
        )
    except Exception as e:
        return f"❌ 港股查询失败: {str(e)}"


# ═════════════════════════════════════════════════════════
# 外汇
# ═════════════════════════════════════════════════════════

FX_NAME_TO_CODE = {
    "美元": "USD", "欧元": "EUR", "日元": "JPY",
    "英镑": "GBP", "港币": "HKD", "人民币": "CNY",
    "加元": "CAD", "澳元": "AUD", "韩元": "KRW",
    "卢布": "RUB", "印度卢比": "INR",
}

FX_CODE_TO_NAME = {v: k for k, v in FX_NAME_TO_CODE.items()}


def query_fx(query):
    """查询汇率 — open.er-api.com"""
    try:
        base_currency = "USD"
        target = "CNY"

        # 检测 "X兑Y" / "X to Y" / "X/Y" 格式
        pair_match = re.search(r"(\w+)\s*(?:兑|to|/)\s*(\w+)", query, re.IGNORECASE)
        if pair_match:
            base_str, target_str = pair_match.groups()
            # base_str 解析
            for name, code in FX_NAME_TO_CODE.items():
                if name in base_str or code in base_str.upper():
                    base_currency = code
                    break
            # target_str 解析
            for name, code in FX_NAME_TO_CODE.items():
                if name in target_str or code in target_str.upper():
                    target = code
                    break
        else:
            # 单个货币名 → 对该货币查人民币汇率
            for name, code in FX_NAME_TO_CODE.items():
                if name in query:
                    target = code
                    break
            if target == base_currency:
                target = "CNY"

        resp = _HTTP.get(f"https://open.er-api.com/v6/latest/{base_currency}", timeout=10)
        data = resp.json()

        if target in data.get("rates", {}):
            rate = data["rates"][target]
            update_time = data.get("time_last_update_utc", "")
            update_str = f"（更新: {update_time}）" if update_time else ""

            base_display = FX_CODE_TO_NAME.get(base_currency, base_currency)
            target_display = FX_CODE_TO_NAME.get(target, target)
            return f"💰 {base_display}（{base_currency}）兑 {target_display}（{target}）: {rate} {update_str}".strip()
        else:
            return f"💰 汇率 {base_currency}->{target} 查询失败"
    except Exception as e:
        return f"❌ 汇率查询失败: {str(e)}"


# ═════════════════════════════════════════════════════════
# 美股指数历史分析
# ═════════════════════════════════════════════════════════
# 美股指数历史分析 + K线图
# ═════════════════════════════════════════════════════════

# 指数 → 新浪美股代码映射
SINA_INDEX_SYMBOLS = {
    "NDX": ".NDX",      # NASDAQ-100
    "COMP": ".IXIC",    # NASDAQ Composite
    "SPX": ".INX",      # S&P 500
    "DJI": ".DJI",      # Dow Jones
}

INDEX_NAMES = {
    "NDX": "NASDAQ-100",
    "COMP": "NASDAQ Composite",
    "SPX": "S&P 500",
    "DJI": "Dow Jones",
}


def _fetch_index_history(symbol, datalen=60):
    """从新浪美股API获取指数日线数据"""

    sina_symbol = SINA_INDEX_SYMBOLS.get(symbol)
    if not sina_symbol:
        return None

    url = (
        "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
        f"var%20data=/US_MinKService.getDailyK"
        f"?symbol={sina_symbol}&datalen={datalen}"
    )
    resp = _HTTP.get(url, headers=SINA_HEADERS, timeout=15)
    raw = resp.text.strip()

    # 提取 JSON 数组
    m = re.search(r"\[.+\]", raw, re.DOTALL)
    if not m:
        return None

    records = json.loads(m.group())
    parsed = []
    for r in records:
        try:
            parsed.append({
                "date": datetime.strptime(r["d"], "%Y-%m-%d"),
                "open": float(r["o"]),
                "high": float(r["h"]),
                "low": float(r["l"]),
                "close": float(r["c"]),
                "volume": int(r["v"]) if r.get("v") and r["v"] != "0" else None,
            })
        except (KeyError, ValueError, TypeError):
            continue

    return parsed


def history_index(symbol):
    """查询美股指数历史走势 — 新浪美股 API"""
    symbol = symbol.upper()
    if symbol not in INDEX_NAMES:
        return f"❌ 不支持的指数: {symbol}（支持: {', '.join(sorted(INDEX_NAMES.keys()))}）"

    name = INDEX_NAMES[symbol]
    try:
        parsed = _fetch_index_history(symbol, datalen=60)
        if not parsed or len(parsed) < 3:
            return f"❌ 未获取到 {name} 历史数据"

        # 只取最近约一个月的交易日
        cutoff = max(1, len(parsed) - 30)
        parsed = parsed[cutoff:]
        # 确保正序
        parsed.sort(key=lambda x: x["date"])

        closes = [d["close"] for d in parsed]
        highs = [d["high"] for d in parsed]
        lows = [d["low"] for d in parsed]

        last = parsed[-1]
        first = parsed[0]

        # --- 指标计算 ---
        period_change = (closes[-1] / closes[0] - 1) * 100

        max_daily_swing = max(
            (h - l) / c * 100 for d, h, l, c in zip(parsed, highs, lows, closes)
        )

        # 最大回撤
        peak = closes[0]
        mdd = 0.0
        mdd_date = ""
        for d, c in zip(parsed, closes):
            if c > peak:
                peak = c
            dd = (c - peak) / peak * 100
            if dd < mdd:
                mdd = dd
                mdd_date = d["date"].strftime("%m/%d")

        # 近一周涨跌
        week_idx = min(5, len(closes) - 1)
        week_change = (closes[-1] / closes[-1 - week_idx] - 1) * 100

        close_fmt = lambda v: f"${v:,.2f}"
        pct_fmt = lambda v: f"{v:+.2f}%"

        lines = [
            f"📊 **{name}**（{symbol}）— 近 {len(parsed)} 个交易日",
            "",
            f"当前: {close_fmt(closes[-1])}  ({pct_fmt(period_change)} 区间)",
            f"近一周: {pct_fmt(week_change)}",
            f"最高: {close_fmt(max(closes))}  最低: {close_fmt(min(closes))}",
            f"最大回撤: {pct_fmt(mdd)}（{mdd_date}）",
            f"日内最大振幅: {pct_fmt(max_daily_swing)}",
            "",
            f"📅 {first['date'].strftime('%m/%d')} — {last['date'].strftime('%m/%d')}",
            f"数据来源: 新浪美股 API",
        ]
        return "\n".join(lines)

    except Exception as e:
        return f"❌ {name} 历史查询失败: {str(e)}"


def generate_chart(parsed, symbol, name):
    """生成 matplotlib 走势图，返回图片路径"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    dates = [d["date"] for d in parsed]
    closes = [d["close"] for d in parsed]
    opens = [d["open"] for d in parsed]
    highs = [d["high"] for d in parsed]
    lows = [d["low"] for d in parsed]

    # ---- 暗色主题图表 ----
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )

    # === 上方：K 线区域填充 + 收盘价线 + 均线 ===
    ax1.fill_between(
        dates, closes, min(closes) * 0.95,
        alpha=0.12, color="#00d4ff",
    )
    ax1.plot(
        dates, closes, color="#00d4ff", linewidth=2.5,
        label="Close", zorder=3,
    )

    # 5日均线
    if len(closes) >= 5:
        ma5 = np.convolve(closes, np.ones(5) / 5, mode="valid")
        ax1.plot(
            dates[4:], ma5, color="#ff6b35", linewidth=1.5,
            linestyle="--", alpha=0.8, label="5-Day MA", zorder=2,
        )

    # 20日均线
    if len(closes) >= 20:
        ma20 = np.convolve(closes, np.ones(20) / 20, mode="valid")
        ax1.plot(
            dates[19:], ma20, color="#ffcc00", linewidth=1.2,
            linestyle="--", alpha=0.6, label="20-Day MA", zorder=2,
        )

    # 最高/最低标注
    max_i = np.argmax(closes)
    min_i = np.argmin(closes)
    ax1.scatter(dates[max_i], closes[max_i], color="#00ff88", s=140, zorder=5, marker="^")
    ax1.scatter(dates[min_i], closes[min_i], color="#ff4466", s=140, zorder=5, marker="v")
    ax1.annotate(
        f"High ${closes[max_i]:,.0f}", (dates[max_i], closes[max_i]),
        textcoords="offset points", xytext=(15, 15),
        fontsize=10, color="#00ff88", fontweight="bold",
    )
    ax1.annotate(
        f"Low ${closes[min_i]:,.0f}", (dates[min_i], closes[min_i]),
        textcoords="offset points", xytext=(15, -20),
        fontsize=10, color="#ff4466", fontweight="bold",
    )

    # 当前价参考线
    pct = (closes[-1] - closes[0]) / closes[0] * 100
    ax1.axhline(y=closes[-1], color="#ffaa00", linewidth=1, linestyle=":", alpha=0.5)
    ax1.annotate(
        f"Latest ${closes[-1]:,.0f} ({pct:+.1f}%)",
        (dates[-1], closes[-1]), textcoords="offset points",
        xytext=(10, 5), fontsize=11, color="#ffaa00", fontweight="bold",
    )

    ax1.set_ylabel("Price (USD)", fontsize=12, color="#ccc")
    ax1.set_title(
        f"{name} ({symbol}) — {parsed[0]['date'].strftime('%m/%d')} ~ {parsed[-1]['date'].strftime('%m/%d')}",
        fontsize=18, fontweight="bold", color="white", pad=20,
    )
    ax1.legend(fontsize=11, loc="upper left")
    ax1.grid(True, alpha=0.12, linestyle="--")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # === 下方：成交量柱状图 ===
    volumes = [d.get("volume") or 0 for d in parsed]
    if any(volumes):
        colors_vol = [
            "#00ff88" if c >= o else "#ff4466"
            for c, o in zip(closes, opens)
        ]
        ax2.bar(dates, volumes, color=colors_vol, alpha=0.5, width=0.8)
        ax2.set_ylabel("Volume", fontsize=11, color="#ccc")
        ax2.grid(True, alpha=0.08, linestyle="--")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

    # X 轴日期
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    fig.autofmt_xdate()
    plt.tight_layout()

    out_path = "/tmp/hermes_index_chart.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    return out_path



# ═════════════════════════════════════════════════════════
# 批量查询
# ═════════════════════════════════════════════════════════

def batch_query(queries):
    """批量查询，结果之间用分割线分隔"""
    results = []
    for q in queries:
        q = q.strip()
        if not q:
            continue
        market_type, identifier = detect_market(q)
        if market_type == "a":
            result = query_a_stock(identifier)
        elif market_type == "us":
            result = query_us_stock(identifier)
        elif market_type == "hk":
            result = query_hk_stock(identifier)
        elif market_type == "fx":
            result = query_fx(identifier)
        else:
            result = f"无法识别市场类型: {q}"
        results.append(result)
    return "\n\n" + ("\n" + "─" * 40 + "\n").join(results)


# ═════════════════════════════════════════════════════════
# A股板块查询（概念 + 行业）
# ═════════════════════════════════════════════════════════

def _load_sector_data(kind="concept"):
    """加载板块数据，返回 {板块名: 涨跌幅} 字典"""
    try:
        import akshare as ak
        if kind == "concept":
            df = ak.stock_sector_spot(indicator="概念")
        else:
            df = ak.stock_sector_spot(indicator="新浪行业")
        return {row["板块"]: row["涨跌幅"] for _, row in df.iterrows()}
    except ImportError:
        return None
    except Exception:
        return None


def _load_concept_flow():
    """加载同花顺资金流向概念数据（387个概念，更全）"""
    try:
        import akshare as ak
        df = ak.stock_fund_flow_concept()
        return {row["行业"]: row["行业-涨跌幅"] for _, row in df.iterrows()}
    except Exception:
        return None


def _fuzzy_match(keyword, name_dict):
    """对关键字进行模糊匹配，返回 (匹配名, 值) 列表"""
    results = []
    keyword_lower = keyword.lower()
    for name, val in name_dict.items():
        if keyword_lower in name.lower():
            results.append((name, val))
    return results


def query_sector(queries, kind="concept"):
    """查询板块涨跌幅

    参数:
        queries: 列表或字符串。["all"] 列出所有板块；否则按名称搜索
        kind: "concept" 概念板块 / "industry" 行业板块
    """
    # 加载数据（优先用资金流向数据，概念板块用这个更全）
    if kind == "concept":
        data = _load_concept_flow() or _load_sector_data("concept")
        label = "📊 A股概念板块"
    else:
        data = _load_sector_data("industry")
        label = "📊 A股行业板块"

    if data is None:
        return "❌ 板块数据加载失败（akshare 可能未安装或 API 异常）"

    lines = []

    # 模式1: 列出所有板块（按涨跌幅降序排列）
    if len(queries) == 1 and queries[0].lower() == "all":
        sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        lines.append(f"{label} — 共 {len(sorted_items)} 个板块")
        lines.append("")
        for name, val in sorted_items:
            cs = "📈" if val > 0 else "📉" if val < 0 else "➡️"
            lines.append(f"  {cs} {name}: {val:+.2f}%")
        return "\n".join(lines)

    # 模式2: 查询特定板块
    for q in queries:
        q = q.strip()
        if not q:
            continue
        # 精确匹配
        if q in data:
            val = data[q]
            cs = "📈" if val > 0 else "📉" if val < 0 else "➡️"
            lines.append(f"{cs} **{q}**: {val:+.2f}%")
        else:
            # 模糊匹配
            matches = _fuzzy_match(q, data)
            if matches:
                for name, val in sorted(matches, key=lambda x: x[1], reverse=True):
                    cs = "📈" if val > 0 else "📉" if val < 0 else "➡️"
                    lines.append(f"{cs} **{name}**: {val:+.2f}%")
            else:
                lines.append(f"❌ 未找到板块「{q}」")

    if not lines:
        return f"{label} 查询无结果"

    return label + "\n\n" + "\n".join(lines)


def list_sectors_summary(top_n=8, kind="concept"):
    data = _load_concept_flow() or _load_sector_data(kind)
    if data is None:
        return "❌ 板块数据加载失败"

    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)

    label = "行业" if kind == "industry" else "概念"
    lines = [f"📊 A股{label}板块速览（共 {len(sorted_items)} 个）", ""]

    # 涨幅前 N
    lines.append(f"🔺 涨幅前 {top_n}：")
    for name, val in sorted_items[:top_n]:
        if val > 0:
            lines.append(f"  📈 {name}: {val:+.2f}%")
        else:
            lines.append(f"  ➡️ {name}: {val:+.2f}%")

    lines.append("")
    lines.append(f"🔻 跌幅前 {top_n}：")
    for name, val in reversed(sorted_items[-top_n:]):
        lines.append(f"  📉 {name}: {val:+.2f}%")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════

def print_usage():
    print("用法:")
    print("  python run.py <股票代码/名称>       # 单条查询")
    print("  python run.py <A,B,C>               # 批量查询（逗号分隔）")
    print("  python run.py --history <INDEX>     # 指数历史分析 (NDX/SPX/DJI/COMP)")
    print("  python run.py --history <INDEX> --chart  # 指数历史 + K线走势图")
    print("  python run.py --sector <名称>        # 查询概念板块涨跌幅")
    print("  python run.py --sector all           # 列出所有概念板块")
    print("  python run.py --sector all --industry # 列出所有行业板块")
    print("  python run.py --sector all --top5     # 概念板块速览（涨跌前5）")
    print()
    print("  示例:")
    print("  python run.py 茅台")
    print("  python run.py AAPL")
    print("  python run.py 00700")
    print("  python run.py 汇率美元")
    print("  python run.py USD/CNY")
    print("  python run.py 茅台,AAPL,00700")
    print("  python run.py --history NDX")
    print("  python run.py --history SPX --chart")
    print("  python run.py --sector CPO,机器人,存储芯片")
    print("  python run.py --sector 半导体")


def main():
    args = sys.argv[1:]
    if not args:
        print_usage()
        sys.exit(0)

    # --help 显示用法
    if args[0] in ("--help", "-h"):
        print_usage()
        sys.exit(0)

    # --sector 模式：查询板块涨跌幅
    if args[0] in ("--sector", "-s"):
        has_industry = "--industry" in args
        has_top = any(a.startswith("--top") for a in args)
        sector_args = [a for a in args[1:] if not a.startswith("--")]

        if has_top:
            top_n = 5
            for a in args[1:]:
                if a.startswith("--top"):
                    try:
                        top_n = int(a.replace("--top", ""))
                    except ValueError:
                        top_n = 5
            kind = "industry" if has_industry else "concept"
            result = list_sectors_summary(top_n=top_n, kind=kind)
            print(result)
            return

        kind = "industry" if has_industry else "concept"

        if not sector_args:
            print("用法: python run.py --sector <板块名称>")
            print("       python run.py --sector all           # 列出所有概念板块")
            print("       python run.py --sector all --industry # 列出所有行业板块")
            print("       python run.py --sector all --top8     # 板块速览前8")
            print("       python run.py --sector CPO,机器人     # 批量查询")
            sys.exit(1)

        # 把所有非--参数合并，按逗号分割
        raw = ",".join(sector_args)
        queries = [q.strip() for q in raw.replace("，", ",").split(",") if q.strip()]
        result = query_sector(queries, kind=kind)
        print(result)
        return

    # --history 模式：指数历史分析（可选 --chart 生成K线图）
    if args[0] == "--history":
        has_chart = "--chart" in args
        index_args = [a for a in args[1:] if a != "--chart"]
        if not index_args:
            print("用法: python run.py --history <INDEX> (NDX/SPX/DJI/COMP)")
            print("       python run.py --history <INDEX> --chart (含K线图)")
            sys.exit(1)
        symbol = index_args[0].upper()
        result = history_index(symbol)
        print(result)
        if has_chart and not result.startswith("❌"):
            parsed = _fetch_index_history(symbol, datalen=60)
            if parsed and len(parsed) >= 5:
                cutoff = max(1, len(parsed) - 30)
                parsed = parsed[cutoff:]
                parsed.sort(key=lambda x: x["date"])
                name = INDEX_NAMES.get(symbol, symbol)
                chart_path = generate_chart(parsed, symbol, name)
                print(f"\n📈 K线走势图已生成: {chart_path}")
                print(f"  （在CLI中可直接打开此文件查看）")
        return

    query = " ".join(args)

    # 检测是否包含逗号分隔 → 批量模式
    if "," in query:
        queries = query.split(",")
        print(batch_query(queries))
        return

    market_type, identifier = detect_market(query)

    if market_type == "a":
        result = query_a_stock(identifier)
    elif market_type == "us":
        result = query_us_stock(identifier)
    elif market_type == "hk":
        result = query_hk_stock(identifier)
    elif market_type == "fx":
        result = query_fx(identifier)
    else:
        result = f"无法识别市场类型: {query}"

    print(result)


if __name__ == "__main__":
    main()
