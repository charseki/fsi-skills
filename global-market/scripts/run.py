#!/usr/bin/env python3
"""全球市场速查 Skill — 自动识别市场并路由到对应数据源"""

import sys
import re
import json
import os
import requests as req
from datetime import datetime, timedelta
import pandas as pd

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

# 图表输出目录（工程目录下的 charts/ 文件夹）
_CHARTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "charts"))
os.makedirs(_CHARTS_DIR, exist_ok=True)


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
                # 优先从市场代码(market_code)字段提取前缀，更准确
                # 如 "sz002938" → "sz"
                if len(parts) >= 4 and parts[3].startswith(("sh", "sz", "us", "hk")):
                    prefix = parts[3][:2]
                else:
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


def _fetch_fund_nav_history(code, days=120):
    """获取基金历史净值数据（用于回撤计算）

    使用 akshare 的 fund_open_fund_info_em 接口，已在腾讯云验证可用。
    返回按日期正序排列的 list[dict]，每项含 date/nav 字段。
    取最近 days 条数据。
    """
    try:
        import akshare as ak
        df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
        if df is None or df.empty:
            return None

        parsed = []
        for _, row in df.iterrows():
            try:
                dt = datetime.strptime(str(row['净值日期']), '%Y-%m-%d')
                nav = float(row['单位净值'])
                parsed.append({'date': dt, 'nav': nav})
            except (ValueError, KeyError, TypeError):
                continue

        if not parsed:
            return None

        parsed.sort(key=lambda x: x['date'])
        if len(parsed) > days:
            parsed = parsed[-days:]
        return parsed
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


def _get_a_prefix(code):
    """根据A股6位代码返回 sh/sz 前缀"""
    if code.startswith(("60", "68")):
        return "sh"
    return "sz"


def _resolve_a_code(query):
    """将A股名称/代码解析为 (sh/sz前缀, 6位代码)；失败返回 None"""
    if re.match(r"^\d{6}$", query):
        return _get_a_prefix(query), query
    try:
        url = f"https://suggest3.sinajs.cn/suggest/?key={query}&type=11,12&count=1"
        resp = _HTTP.get(url, headers=SINA_HEADERS, timeout=10)
        raw = resp.text.strip()
        if "suggestvalue=" in raw:
            data = raw.split('"')[1]
            if data and data != ";":
                items = data.strip(";").split(";")
                if items:
                    parts = items[0].split(",")
                    if len(parts) >= 3:
                        code = parts[2]
                        # 优先从市场代码(market_code)字段提取前缀
                        if len(parts) >= 4 and parts[3].startswith(("sh", "sz", "us", "hk")):
                            prefix = parts[3][:2]
                        else:
                            flag = parts[1]
                            prefix = "sh" if flag == "11" else "sz" if flag == "12" else flag
                        return prefix, code
    except Exception:
        pass
    return None


def _fetch_stock_history(market_type, identifier, days=120):
    """获取个股近90个交易日K线数据

    参数:
        market_type: "a" / "us" / "hk"
        identifier: 代码或名称（A股支持中文名）
        days: 请求的日历天数（需比90交易日多）
    返回:
        list[dict] | None — 每个 dict 含 date/open/high/low/close/volume
    """
    if market_type == "us":
        # === 美股/指数 → 新浪 US_MinKService API ===
        index_map = {"SPX": ".INX", "DJI": ".DJI", "NDX": ".NDX", "COMP": ".IXIC"}
        sina_symbol = index_map.get(identifier.upper(), identifier.upper())

        url = (
            "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/"
            f"var%20data=/US_MinKService.getDailyK"
            f"?symbol={sina_symbol}&datalen={days}"
        )
        resp = _HTTP.get(url, headers=SINA_HEADERS, timeout=15)
        raw = resp.text.strip()

        # 市前可能有 script 重定向注释
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
                    "volume": int(float(r.get("v", 0))) if r.get("v") and r["v"] != "0" else 0,
                })
            except (KeyError, ValueError, TypeError):
                continue
        return parsed if parsed else None

    elif market_type == "a":
        # === A股 → Tencent ifzq API（qfqday = 前复权日线）===
        resolved = _resolve_a_code(identifier)
        if not resolved:
            return None
        prefix, code = resolved

        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={prefix}{code},day,,,{days},qfq"
        )
        resp = _HTTP.get(url, timeout=15)
        data = resp.json()

        try:
            records = data["data"][f"{prefix}{code}"]["qfqday"]
        except (KeyError, TypeError):
            # 部分股票可能没有 qfqday，试 day
            try:
                records = data["data"][f"{prefix}{code}"]["day"]
            except (KeyError, TypeError):
                return None

        if not records:
            return None

        parsed = []
        for r in records:
            try:
                # ifzq 格式: [date, open, close, high, low, volume]
                dt = datetime.strptime(r[0], "%Y-%m-%d")
                parsed.append({
                    "date": dt,
                    "open": float(r[1]),
                    "close": float(r[2]),
                    "high": float(r[3]),
                    "low": float(r[4]),
                    "volume": int(float(r[5])),
                })
            except (IndexError, ValueError, TypeError):
                continue

        return parsed if parsed else None

    elif market_type == "hk":
        # === 港股 → Tencent ifzq API（无前复权，day = 日线）===
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param=hk{identifier},day,,,{days},qfq"
        )
        resp = _HTTP.get(url, timeout=15)
        data = resp.json()

        try:
            records = data["data"][f"hk{identifier}"]["day"]
        except (KeyError, TypeError):
            return None

        if not records:
            return None

        parsed = []
        for r in records:
            try:
                # day 格式: [date, open, close, high, low, volume, ...extra]
                dt = datetime.strptime(r[0], "%Y-%m-%d")
                parsed.append({
                    "date": dt,
                    "open": float(r[1]),
                    "close": float(r[2]),
                    "high": float(r[3]),
                    "low": float(r[4]),
                    "volume": int(float(r[5])),
                })
            except (IndexError, ValueError, TypeError):
                continue

        return parsed if parsed else None

    return None


def parse_chart_params(raw_query):
    """从查询字符串中解析动态K线图表参数

    支持的输入格式：
      "002938,K120,[MA20,MA45,MA120]"  → 120日K线 + 3条均线
      "茅台,K60,[MA10,MA20]"           → 60日 + 2条均线
      "AAPL,[MA50,MA100,MA200]"        → 默认90日 + 3条均线
      "00700,K200"                     → 200日 + 默认MA20/MA90
      "茅台"                            → 无图表参数 (返回 None)

    返回:
        (stock_query, k_period, ma_periods)  或 None
    """
    # 先提取 [...] 中的均线列表（不分割内部逗号）
    ma_match = re.search(r"\[([^\]]*?MA\d+[^\]]*?)\]", raw_query, re.IGNORECASE)
    ma_periods = None
    remaining = raw_query

    if ma_match:
        ma_content = ma_match.group(1)
        periods = re.findall(r"MA(\d+)", ma_content, re.IGNORECASE)
        if periods:
            ma_periods = [int(p) for p in periods]
        remaining = raw_query.replace(ma_match.group(0), "").strip()

    # 在剩余字符串中提取 K<天数>
    k_match = re.search(r"(?:^|[,;\s]+)K(\d+)(?=$|[,;\s]+)", remaining, re.IGNORECASE)
    k_period = int(k_match.group(1)) if k_match else None

    if k_period is None and ma_periods is None:
        return None  # 无图表参数

    # 从 remaining 中移除 K<天数> 片段
    stock_query = remaining
    if k_match:
        stock_query = remaining.replace(k_match.group(0), "").strip()

    # 清理残留的逗号和空格
    stock_query = re.sub(r"[,;\s]+", " ", stock_query).strip()
    stock_query = stock_query.replace(" ", ",") if "," in raw_query else stock_query

    k_period = k_period or 90
    ma_periods = ma_periods or [20, 90]
    return stock_query, k_period, ma_periods


def parse_drawdown_params(raw_query):
    """从查询字符串中解析回撤图表参数

    格式: <代码/名称>,HC<N>
    如: 007467,HC30, 013275,HC90, 600519,HC30, 茅台,HC30
    返回: (stock_query, hc_days)  或 None
    """
    m = re.search(r"[,;，\s]*[Hh][Cc](\d+)\s*$", raw_query)
    if not m:
        return None
    hc_days = int(m.group(1))
    stock_query = raw_query[:m.start()].strip().rstrip(",;， ")
    return stock_query, hc_days


def generate_stock_chart(parsed, name, code, market_type="a", ma_periods=None, k_period=90):
    """生成个股K线趋势图（K线实体 + 动态MA均线 + 成交量）

    参数:
        parsed: _fetch_stock_history() 返回的数据
        name: 股票显示名
        code: 股票代码
        market_type: a/us/hk
        ma_periods: 均线周期列表，如 [20, 45, 120]
        k_period: K线展示的天数（交易日），如 120
    返回:
        图片路径（skill 目录下的 charts/ 文件夹，按参数动态命名如 002938_K120_MA20_MA45_MA120.png）
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm
    import numpy as np
    from matplotlib.patches import Rectangle

    # —— 注册中文字体 ——
    _CJK_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    if _CJK_FONT:
        fm.fontManager.addfont(_CJK_FONT)
        plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    plt.rcParams["axes.unicode_minus"] = False

    if ma_periods is None:
        ma_periods = [20, 90]

    # 排序（保留全部数据用于均线计算，画图时再限定展示范围）
    parsed.sort(key=lambda x: x["date"])

    dates = [d["date"] for d in parsed]
    opens = np.array([d["open"] for d in parsed])
    highs = np.array([d["high"] for d in parsed])
    lows = np.array([d["low"] for d in parsed])
    closes = np.array([d["close"] for d in parsed])

    # 成交量：A股手数×收盘价/10000=成交额(百万元)，美股/港股保持原始股数
    vol_raw = np.array([d.get("volume", 0) for d in parsed])
    if market_type == "a":
        volumes = vol_raw * closes / 10000.0
        VOL_LABEL = "成交额(百万元)"
    elif market_type == "hk":
        volumes = vol_raw
        VOL_LABEL = "成交量(股)"
    else:
        volumes = vol_raw
        VOL_LABEL = "Volume"

    # 货币符号
    sym_cur = "$" if market_type in ("us",) else "HK$" if market_type == "hk" else "¥"
    label_price = "Price (USD)" if market_type == "us" else "Price (HKD)" if market_type == "hk" else "价格 (元)"

    # —— 动态均线配色（最多8条，循环）——
    MA_COLORS = ["#ffcc00", "#ff6bff", "#00d4ff", "#ff6b35", "#88ff88", "#ff4466", "#00ffff", "#ffffff"]

    # ---- 暗色主题 ----
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    fig.patch.set_facecolor("#1a1a2e")

    # —— K线颜色惯例：亚洲红涨绿跌 / 欧美绿涨红跌 ——
    if market_type in ("a", "hk"):
        UP_COLOR = "#ff4466"    # 红 = 阳线(上涨)
        DOWN_COLOR = "#00ff88"  # 绿 = 阴线(下跌)
    else:
        UP_COLOR = "#00ff88"    # 绿 = 上涨
        DOWN_COLOR = "#ff4466"  # 红 = 下跌

    # —— K线 ——
    x_dates = mdates.date2num(dates)
    if len(dates) > 1:
        candle_w = (x_dates[1] - x_dates[0]) * 0.7
    else:
        candle_w = 0.6

    for i in range(len(dates)):
        x = x_dates[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        up = c >= o
        color = UP_COLOR if up else DOWN_COLOR

        # 影线
        ax1.plot([x, x], [l, h], color=color, linewidth=0.7, alpha=0.5)

        # 实体
        body_bottom = min(o, c)
        body_height = abs(c - o) or 0.005
        rect = Rectangle(
            (x - candle_w / 2, body_bottom), candle_w, body_height,
            facecolor=color, edgecolor=color, alpha=0.85, linewidth=0.5,
        )
        ax1.add_patch(rect)

    # —— 动态均线 ——
    drawn_ma = []
    for i, period in enumerate(ma_periods):
        if len(closes) >= period:
            ma = np.convolve(closes, np.ones(period) / period, mode="valid")
            color = MA_COLORS[i % len(MA_COLORS)]
            ax1.plot(
                dates[period - 1:], ma, color=color, linewidth=1.6,
                linestyle="--", alpha=0.7, label=f"MA{period}", zorder=3,
            )
            drawn_ma.append(period)

    # —— 当前价参考线 ——
    pct = (closes[-1] - closes[0]) / closes[0] * 100
    ax1.axhline(y=closes[-1], color="#ffaa00", linewidth=1, linestyle=":", alpha=0.5)
    ax1.annotate(
        f"最新 {sym_cur}{closes[-1]:.2f}  ({pct:+.2f}%)",
        (dates[-1], closes[-1]), textcoords="offset points",
        xytext=(10, 8), fontsize=11, color="#ffaa00", fontweight="bold",
    )

    # —— 最高/最低标注 ——
    max_i = int(np.argmax(highs))
    min_i = int(np.argmin(lows))
    ax1.scatter(dates[max_i], highs[max_i], color="#00ff88", s=120, zorder=5, marker="^")
    ax1.scatter(dates[min_i], lows[min_i], color="#ff4466", s=120, zorder=5, marker="v")
    ax1.annotate(
        f"最高 {sym_cur}{highs[max_i]:.2f}",
        (dates[max_i], highs[max_i]), textcoords="offset points",
        xytext=(12, 12), fontsize=9, color="#88ffbb", fontweight="bold",
    )
    ax1.annotate(
        f"最低 {sym_cur}{lows[min_i]:.2f}",
        (dates[min_i], lows[min_i]), textcoords="offset points",
        xytext=(12, -16), fontsize=9, color="#ff8899", fontweight="bold",
    )

    ax1.set_ylabel(label_price, fontsize=12, color="#ccc")
    # 动态标题
    ma_label = "+".join([str(p) for p in drawn_ma])
    ax1.set_title(
        f"{name}（{code}）— {dates[-k_period].strftime('%m/%d') if len(dates) > k_period else dates[0].strftime('%m/%d')} ~ {dates[-1].strftime('%m/%d')}"
        f"  |  {k_period}日K线  MA{ma_label}",
        fontsize=16, fontweight="bold", color="white", pad=18,
    )
    ax1.legend(fontsize=11, loc="upper left")
    ax1.grid(True, alpha=0.1, linestyle="--")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # —— 成交量柱状图 ——
    if any(volumes):
        vol_colors = [
            UP_COLOR if c >= o else DOWN_COLOR
            for c, o in zip(closes, opens)
        ]
        ax2.bar(dates, volumes, color=vol_colors, alpha=0.4, width=candle_w * 1.1)
        ax2.set_ylabel(VOL_LABEL, fontsize=11, color="#ccc")
        ax2.grid(True, alpha=0.07, linestyle="--")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

    # X 轴日期
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    if len(dates) > 20:
        ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    fig.autofmt_xdate()
    plt.tight_layout()

    # 限定展示范围为最近 k_period 个交易日（保留历史数据用于均线计算）
    if len(dates) > k_period:
        x_start = dates[-k_period]
        x_end = dates[-1]
        ax1.set_xlim(x_start, x_end)
        ax2.set_xlim(x_start, x_end)

    # —— 动态文件名（用传入的参数而非实际绘制的） ——
    ma_part = "_".join([f"MA{p}" for p in ma_periods])
    code_safe = re.sub(r"[^A-Za-z0-9]", "", code)
    filename = f"{code_safe}_K{k_period}_{ma_part}.png"
    out_path = os.path.join(_CHARTS_DIR, filename)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    return out_path


def generate_drawdown_chart(nav_data, name, code, days):
    """生成回撤折线图（暗色主题）

    参数:
        nav_data: list[dict] — 含 date/nav（基金）或 date/close（股票）
        name, code: 显示名称和代码
        days: 回撤统计交易日数
    返回: 图片路径（charts/ 下）
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm
    import numpy as np

    # 注册中文字体
    _CJK_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    if _CJK_FONT:
        fm.fontManager.addfont(_CJK_FONT)
        plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    plt.rcParams["axes.unicode_minus"] = False

    # 提取数值序列
    sorted_data = sorted(nav_data, key=lambda x: x["date"])
    dates = [d["date"] for d in sorted_data]
    if "nav" in sorted_data[0]:
        values = np.array([d["nav"] for d in sorted_data])
    else:
        values = np.array([d["close"] for d in sorted_data])

    # 计算回撤：drawdown = (value - peak) / peak * 100
    peak = np.maximum.accumulate(values)
    drawdown = (values - peak) / peak * 100

    # 最大回撤
    max_dd_idx = int(np.argmin(drawdown))
    max_dd = drawdown[max_dd_idx]
    max_dd_date = dates[max_dd_idx]
    current_dd = drawdown[-1]

    # 暗色主题
    plt.style.use("dark_background")
    fig, ax = plt.subplots(1, 1, figsize=(14, 7))
    fig.patch.set_facecolor("#1a1a2e")

    # 回撤填充区域 + 折线
    ax.fill_between(dates, 0, drawdown, where=drawdown < 0,
                    color="#ff4466", alpha=0.15, step="pre")
    ax.plot(dates, drawdown, color="#ff4466", linewidth=2.0, zorder=3)

    # 零线
    ax.axhline(y=0, color="#555555", linewidth=1, linestyle="-", alpha=0.5)

    # 最大回撤标注
    ax.scatter(max_dd_date, max_dd, color="#ff0000", s=140, zorder=5, marker="v")
    ax.annotate(
        f"最大回撤 {max_dd:.2f}%\n{max_dd_date.strftime('%Y-%m-%d')}",
        (max_dd_date, max_dd), textcoords="offset points",
        xytext=(20, -35), fontsize=11, color="#ff6666",
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#ff6666", lw=1.5),
    )

    # 当前回撤标注
    ax.annotate(
        f"当前回撤 {current_dd:.2f}%",
        (dates[-1], drawdown[-1]), textcoords="offset points",
        xytext=(10, 10), fontsize=12, color="#ffaa00", fontweight="bold",
    )

    ax.set_ylabel("回撤 (%)", fontsize=12, color="#ccc")
    ax.set_title(
        f"{name}（{code}）— 近{days}个交易日回撤走势",
        fontsize=16, fontweight="bold", color="white", pad=18,
    )
    y_bottom = min(drawdown) * 1.15
    y_top = max(max(drawdown) * 1.5 + 2, 5) if any(d < 0 for d in drawdown) else 2
    ax.set_ylim(y_bottom, y_top)

    ax.grid(True, alpha=0.12, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # X 轴日期
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    if len(dates) > 20:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    fig.autofmt_xdate()
    plt.tight_layout()

    code_safe = re.sub(r"[^A-Za-z0-9]", "", code)
    filename = f"{code_safe}_HC{days}.png"
    out_path = os.path.join(_CHARTS_DIR, filename)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    return out_path


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

    # —— 动态文件名 ——
    sym_safe = re.sub(r"[^A-Za-z0-9]", "", symbol)
    filename = f"{sym_safe}_history.png"
    out_path = os.path.join(_CHARTS_DIR, filename)
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
    print("  python run.py <代码/名称> --chart   # 单条查询 + 90日K线趋势图(含MA20/MA90)")
    print("  python run.py \"<代码>,K<天数>,[MA<周期>,...]\"  # 动态K线 + 动态均线")
    print("                                         # 如: 002938,K120,[MA20,MA45,MA120]")
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
    print("  python run.py 茅台 --chart")
    print("  python run.py AAPL --chart")
    print("  python run.py 00700 --chart")
    print("  python run.py 600519 --chart")
    print("  python run.py 汇率美元")
    print("  python run.py USD/CNY")
    print("  python run.py 茅台,AAPL,00700")
    print("  python run.py --history NDX")
    print("  python run.py --history SPX --chart")
    print("  python run.py --sector CPO,机器人,存储芯片")
    print("  python run.py --sector 半导体")
    print()
    print("  动态图表示例:")
    print("  python run.py \"002938,K120,[MA20,MA45,MA120]\"")
    print("  python run.py \"茅台,K60,[MA10,MA20,MA30]\"")
    print("  python run.py \"AAPL,[MA50,MA100,MA200]\"")
    print()
    print("  回撤折线图 (HC = Drawdown):")
    print("  python run.py \"007467,HC30\"     # 华泰柏瑞红利低波联接C, 30日回撤")
    print("  python run.py \"013275,HC90\"     # 富国中证煤炭C, 90日回撤")
    print("  python run.py \"600519,HC60\"     # 茅台, 60日回撤")
    print("  python run.py \"茅台,HC30\"        # 茅台名称搜索, 30日回撤")


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

    has_chart = "--chart" in args

    # 对股票查询：去掉 --chart 后再拼接查询字符串
    stock_args = [a for a in args if a != "--chart"]
    raw_query = " ".join(stock_args)

    # === 回撤折线图 (HC) 模式 ===
    parsed_hc = parse_drawdown_params(raw_query)
    if parsed_hc:
        hc_stock_query, hc_days = parsed_hc
        hc_market, hc_id = detect_market(hc_stock_query)

        # 获取显示名称 + 历史数据
        hc_display_name = hc_stock_query
        hc_code = re.sub(r"[^A-Za-z0-9]", "", hc_stock_query)
        hc_hist = None

        # 6 位数字：先试基金，再试 A 股
        if re.match(r"^\d{6}$", hc_stock_query):
            fund_info = query_fund(hc_stock_query)
            if fund_info and not fund_info.startswith("❌"):
                name_m = re.search(r"\*\*(.+?)\*\*", fund_info)
                hc_display_name = name_m.group(1) if name_m else hc_stock_query
                hc_code = hc_stock_query
                hc_hist = _fetch_fund_nav_history(hc_stock_query, days=hc_days * 2)
                if not hc_hist:
                    print(f"❌ 未获取到基金「{hc_stock_query}」历史净值数据")
                    return
            else:
                # 不是基金，走 A 股
                resolved = _resolve_a_code(hc_stock_query)
                if not resolved:
                    print(f"❌ 未找到「{hc_stock_query}」")
                    return
                a_prefix, a_code = resolved
                a_result = _tx_fetch(f"{a_prefix}{a_code}")
                if a_result:
                    hc_display_name = a_result[1]
                    hc_code = a_code
                hc_hist = _fetch_stock_history("a", hc_stock_query, days=hc_days * 2)

        elif hc_market == "a":
            # 中文名称或非标准代码 → A 股
            resolved = _resolve_a_code(hc_stock_query)
            if not resolved:
                print(f"❌ 未找到 A 股「{hc_stock_query}」")
                return
            a_prefix, a_code = resolved
            a_result = _tx_fetch(f"{a_prefix}{a_code}")
            if a_result:
                hc_display_name = a_result[1]
                hc_code = a_code
            hc_hist = _fetch_stock_history("a", hc_stock_query, days=hc_days * 2)

        elif hc_market == "us":
            us_result = query_us_stock(hc_stock_query)
            if not us_result.startswith("❌"):
                name_m = re.search(r"\*\*(.+?)\*\*", us_result)
                hc_display_name = name_m.group(1) if name_m else hc_stock_query
                hc_code = hc_stock_query.upper()
            hc_hist = _fetch_stock_history("us", hc_stock_query, days=hc_days * 2)

        elif hc_market == "hk":
            hk_result = query_hk_stock(hc_id)
            if not hk_result.startswith("❌"):
                name_m = re.search(r"\*\*(.+?)\*\*", hk_result)
                hc_display_name = name_m.group(1) if name_m else hc_stock_query
                hc_code = hc_id
            hc_hist = _fetch_stock_history("hk", hc_id, days=hc_days * 2)

        else:
            print(f"❌ 不支持的回撤查询市场类型: {hc_stock_query}")
            return

        if not hc_hist or len(hc_hist) < 3:
            print(f"⚠️ 未获取到足够的K线数据（当前{len(hc_hist) if hc_hist else 0}条，需≥3条）")
            return

        # 只取最近 hc_days 个交易日
        if len(hc_hist) > hc_days:
            hc_hist = hc_hist[-hc_days:]

        try:
            chart_path = generate_drawdown_chart(hc_hist, hc_display_name, hc_code, hc_days)
            print(f"📉 回撤折线图已生成: {chart_path}")
            print(f"   标的: {hc_display_name}（{hc_code}） | 回撤区间: {hc_days}个交易日")
            # 简要回撤摘要
            vals = [d.get('nav', d.get('close', 0)) for d in hc_hist]
            peak_v = max(vals)
            cur_v = vals[-1]
            dd = (cur_v - peak_v) / peak_v * 100
            max_d = min((v - max(vals[:i+1])) / max(vals[:i+1]) * 100 
                       for i, v in enumerate(vals))
            print(f"   当前回撤: {dd:.2f}% | 区间最大回撤: {min(max_d, dd):.2f}%")
        except Exception as e:
            print(f"⚠️ 回撤图生成失败: {str(e)}")
        return

    # 检测动态图表参数（新格式: "002938,K120,[MA20,MA45,MA120]"）
    parsed_chart = parse_chart_params(raw_query)
    has_dynamic_chart = parsed_chart is not None

    if has_dynamic_chart:
        chart_stock_query, chart_k_period, chart_ma_periods = parsed_chart
        query = chart_stock_query
    else:
        chart_k_period = 90
        chart_ma_periods = [20, 90]
        query = raw_query

    # 检测是否包含逗号分隔 → 批量模式（仅非动态图表模式）
    if not has_dynamic_chart and "," in query:
        print(batch_query(query.split(",")))
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

    # 图表生成条件：--chart 或动态参数
    should_chart = (has_chart or has_dynamic_chart) \
                   and market_type in ("a", "us", "hk") \
                   and not result.startswith("❌")

    if should_chart:
        name_match = re.search(r"\*\*(.+?)\*\*", result)
        display_name = name_match.group(1) if name_match else identifier

        # 获取实际股票代码用于文件名（A股名称→6位代码）
        if market_type == "a":
            resolved = _resolve_a_code(identifier)
            chart_code = resolved[1] if resolved else re.sub(r"[^A-Za-z0-9]", "", identifier)
        else:
            chart_code = identifier.upper()

        try:
            # 请求足够多的数据（交易日 * 2 确保覆盖）
            hist = _fetch_stock_history(market_type, identifier, days=max(120, chart_k_period * 2))
            min_required = min(10, chart_k_period)
            if hist and len(hist) >= min_required:
                chart_path = generate_stock_chart(
                    hist, display_name, chart_code, market_type,
                    ma_periods=chart_ma_periods, k_period=chart_k_period,
                )
                ma_label = "MA" + "+".join(str(p) for p in chart_ma_periods if len(hist) >= p)
                print(f"\n📈 {chart_k_period}日K线趋势图已生成: {chart_path}")
                print(f"   均线: {ma_label}")
            else:
                print(f"\n⚠️ 未获取到足够的K线数据（当前{len(hist) if hist else 0}条，需≥{min_required}条）")
        except Exception as e:
            print(f"\n⚠️ K线图生成失败: {str(e)}")


if __name__ == "__main__":
    main()
