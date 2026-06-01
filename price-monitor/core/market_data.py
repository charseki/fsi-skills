"""
market_data.py — 统一市场数据获取层

封装从 global-market 验证过的数据源，为量化策略提供一致的接口。
数据源（已验证腾讯云可用）：
  - A股/ETF行情：腾讯 qt.gtimg.cn
  - 港股行情：新浪 hq.sinajs.cn
  - 美股行情：腾讯 qt.gtimg.cn
  - A股/港股历史日K：Tencent ifzq API
  - 美股历史日K：新浪 US_MinKService
  - 基金净值/历史：天天基金 fundgz + akshare
  - 外汇：open.er-api.com
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests as req

# ── 环境 ──────────────────────────────────────────────
_SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CHARTS_DIR = os.path.join(_SKILL_DIR, "reports", "signals")
os.makedirs(CHARTS_DIR, exist_ok=True)

SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}
_HTTP = req.Session()

# ── Helpers ───────────────────────────────────────────

def _parse_tencent_vX(blob: str) -> dict | None:
    """解析腾讯 qt.gtimg.cn 返回值，返回字段 dict 或 None"""
    m = re.search(r'v_[^=]+=\"(.+)\"', blob)
    if not m:
        return None
    parts = m.group(1).split("~")
    if len(parts) < 3:
        return None
    return {
        "name": parts[1],
        "code": parts[2],
        "price": _f(parts[3]),
        "prev_close": _f(parts[4]),
        "open": _f(parts[5]),
        "volume": parts[6] if len(parts) > 6 else "0",
        "change": _f(parts[31]) if len(parts) > 31 else 0,
        "chg_pct": _f(parts[32]) if len(parts) > 32 else 0,
        "high": _f(parts[33]) if len(parts) > 33 else 0,
        "low": _f(parts[34]) if len(parts) > 34 else 0,
    }

def _f(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def _resolve_a_code(code_or_name: str) -> tuple[str, str]:
    """将 A 股名称或代码解析为 (市场前缀, 代码)"""
    if re.fullmatch(r'\d{6}', code_or_name):
        return ("sh" if code_or_name.startswith(("5", "6", "9")) else "sz", code_or_name)
    # 名称搜索 → 新浪建议接口
    try:
        r = _HTTP.get(
            f"https://suggest3.sinajs.cn/suggest/?key={code_or_name}&type=11,12",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=8,
        )
        r.encoding = "gbk"
        parts = r.text.split(";")
        for p in parts:
            cols = p.split(",")
            if len(cols) >= 4 and re.fullmatch(r'\d{6}', cols[2]):
                code = cols[2]
                pref = "sh" if code.startswith(("5", "6", "9")) else "sz"
                return (pref, code)
    except Exception:
        pass
    raise ValueError(f"无法解析 A 股代码/名称: {code_or_name}")

# ── 实时行情 ──────────────────────────────────────────

def quote_a(code_or_name: str) -> dict | None:
    """A 股实时行情"""
    pref, code = _resolve_a_code(code_or_name)
    try:
        r = _HTTP.get(f"https://qt.gtimg.cn/q={pref}{code}", timeout=8)
        r.encoding = "gbk"
        return _parse_tencent_vX(r.text)
    except Exception:
        return None

def quote_us(symbol: str) -> dict | None:
    """美股实时行情"""
    try:
        r = _HTTP.get(f"https://qt.gtimg.cn/q=us{symbol}", timeout=8)
        r.encoding = "gbk"
        return _parse_tencent_vX(r.text)
    except Exception:
        return None

def quote_hk(code_5: str) -> dict | None:
    """港股实时行情"""
    code = code_5.zfill(5)
    try:
        r = _HTTP.get(
            f"https://hq.sinajs.cn/list=hk{code}",
            headers=SINA_HEADERS,
            timeout=8,
        )
        r.encoding = "gbk"
        m = re.search(r'hq_str_hk\w+="(.+)"', r.text)
        if not m:
            return None
        parts = m.group(1).split(",")
        if len(parts) < 12:
            return None
        return {
            "name": parts[1],
            "price": _f(parts[2]),
            "prev_close": _f(parts[3]),
            "high": _f(parts[4]),
            "low": _f(parts[5]),
            "open": _f(parts[6]),
            "change": _f(parts[7]),
            "chg_pct": _f(parts[8]),
            "volume": parts[12] if len(parts) > 12 else "0",
            "amount": parts[11] if len(parts) > 11 else "0",
        }
    except Exception:
        return None

def quote_fund(code_6: str) -> dict | None:
    """基金实时估算净值（天天基金 fundgz）"""
    try:
        r = _HTTP.get(f"https://fundgz.1234567.com.cn/js/{code_6}.js", timeout=8)
        m = re.search(r'jsonpgz\((.+)\)', r.text)
        if not m:
            return None
        d = json.loads(m.group(1))
        return {
            "name": d.get("name"),
            "code": d.get("fundcode"),
            "nav_date": d.get("jzrq"),
            "nav": _f(d.get("dwjz", 0)),
            "gsz": _f(d.get("gsz", 0)),
            "gszzl": _f(d.get("gszzl", 0)),
            "gztime": d.get("gztime"),
        }
    except Exception:
        return None

# ── 自动路由 ──────────────────────────────────────────

MARKET_PATTERNS = [
    ("fx", lambda q: any(kw in q for kw in ["汇率", "美元", "欧元", "日元", "英镑",
                                              "港币", "USD", "CNY", "EUR", "JPY", "GBP"])),
    ("hk", lambda q: (re.fullmatch(r'\d{5}', q) is not None) or q.endswith(".HK")),
    ("us", lambda q: re.fullmatch(r'[A-Za-z]{1,5}', q) is not None and q.upper() not in {"SH", "SZ", "HSI"}),
    ("fund", lambda q: re.fullmatch(r'\d{6}', q) is not None and q.startswith(("0", "01"))),
    ("a", lambda q: re.fullmatch(r'\d{6}', q) is not None or not re.fullmatch(r'[A-Za-z]{1,5}', q)),
]

def detect_market(query: str) -> str:
    """返回市场类型: a / us / hk / fund / fx"""
    q = query.strip().upper()
    for mtype, matcher in MARKET_PATTERNS:
        if matcher(q):
            return mtype
    return "a"

def unified_quote(query: str) -> dict | None:
    """
    统一入口：根据 query 自动路由到对应数据源
    返回: {"market": str, "data": dict, ...}
    """
    market = detect_market(query)
    result = {"market": market, "query": query, "data": None}

    if market == "a":
        # 6位数字先试基金再试 A 股
        if re.fullmatch(r'\d{6}', query) and query.startswith(("0", "01")):
            data = quote_fund(query)
            if data:
                result["market"] = "fund"
                result["data"] = data
                return result
        data = quote_a(query)
        if data:
            result["data"] = data
            return result
        # 再试基金兜底
        if re.fullmatch(r'\d{6}', query):
            data = quote_fund(query)
            if data:
                result["market"] = "fund"
                result["data"] = data
                return result
    elif market == "fund":
        data = quote_fund(query)
        if data:
            result["data"] = data
            return result
        # fund 查不到降级为 A 股
        data = quote_a(query)
        if data:
            result["market"] = "a"
            result["data"] = data
            return result
    elif market == "us":
        data = quote_us(query)
        if data:
            result["data"] = data
            return result
    elif market == "hk":
        data = quote_hk(query)
        if data:
            result["data"] = data
            return result

    return result

# ── 历史日K ───────────────────────────────────────────

def fetch_history(market_type: str, identifier: str, days: int = 120) -> pd.DataFrame | None:
    """
    获取历史日K线数据，返回 DataFrame（列: date, open, close, high, low, volume）
    支持 a / us / hk
    """
    if market_type == "a":
        return _fetch_ifzq(identifier, "sh" if identifier.startswith(("5", "6", "9")) else "sz", days)
    elif market_type == "hk":
        return _fetch_ifzq(identifier.zfill(5), "hk", days, fq=False)
    elif market_type == "us":
        return _fetch_sina_us(identifier, days)
    elif market_type == "fund":
        return _fetch_fund_nav(identifier, days)
    return None


def _fetch_ifzq(code: str, prefix: str, days: int = 120, fq: bool = True) -> pd.DataFrame | None:
    """Tencent ifzq API — A股/港股日K线"""
    try:
        url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
               f"?param={prefix}{code},day,,,{days},qfq")
        r = _HTTP.get(url, timeout=10)
        d = r.json()
        # ifzq 返回的 key 是 prefix+code（如 sh512890），不是纯 code
        full_key = f"{prefix}{code}"
        records = d.get("data", {}).get(full_key, {}) or d.get("data", {}).get(code, {})
        if fq:
            klines = records.get("qfqday") or records.get("day")
        else:
            klines = records.get("day")
        if not klines:
            return None
        rows = []
        for row in klines:
            if len(row) >= 6:
                rows.append({
                    "date": row[0],
                    "open": float(row[1]),
                    "close": float(row[2]),
                    "high": float(row[3]),
                    "low": float(row[4]),
                    "volume": float(row[5]),
                })
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _fetch_sina_us(symbol: str, days: int = 120) -> pd.DataFrame | None:
    """新浪 US_MinKService API — 美股日K线"""
    try:
        url = ("https://stock.finance.sina.com.cn/usstock/api/"
               f"jsonp.php/var%20data=/US_MinKService.getDailyK?symbol={symbol}&datalen={days}")
        r = _HTTP.get(url, headers=SINA_HEADERS, timeout=15)
        # 先去掉前导的 JS 代码前缀
        text = r.text
        idx = text.find("data=")
        if idx < 0:
            return None
        json_str = text[idx + 5:].strip().rstrip(";").rstrip()
        # 去除可能的括号包裹：data=([...]) 或 data=[...]
        if json_str.startswith("(") and json_str.endswith(")"):
            json_str = json_str[1:-1]
        raw = json.loads(json_str)
        rows = []
        for row in raw:
            if isinstance(row, dict):
                rows.append({
                    "date": row.get("d", ""),
                    "open": float(row.get("o", 0)),
                    "close": float(row.get("c", 0)),
                    "high": float(row.get("h", 0)),
                    "low": float(row.get("l", 0)),
                    "volume": float(row.get("v", 0)),
                })
            elif isinstance(row, (list, tuple)) and len(row) >= 8:
                rows.append({
                    "date": row[0],
                    "open": float(row[1]),
                    "close": float(row[4]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "volume": float(row[7]) if row[7] else 0,
                })
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _fetch_fund_nav(code_6: str, days: int = 120) -> pd.DataFrame | None:
    """基金历史净值 — akshare fund_open_fund_info_em"""
    try:
        import akshare as ak
        df = ak.fund_open_fund_info_em(symbol=code_6, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        df = df.rename(columns={"净值日期": "date", "单位净值": "close", "日增长率": "chg_pct"})
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").tail(days).reset_index(drop=True)
        return df
    except Exception:
        return None


def fetch_batch(symbols: list[str], days: int = 120) -> dict[str, pd.DataFrame | None]:
    """批量获取多个标的历史数据"""
    result = {}
    for sym in symbols:
        market = detect_market(sym)
        result[sym] = fetch_history(market, sym, days)
        time.sleep(0.3)  # 防止限流
    return result
