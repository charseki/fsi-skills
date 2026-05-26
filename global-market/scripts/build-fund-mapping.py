#!/usr/bin/env python3
"""
Build optimized sector→fund mapping from lof-mapping.md.

Fetches current NAV + historical NAV for all funds in lof-mapping.md,
generates an updated etf-mapping.md and fund-nav-history.csv.

Usage:
  source ~/venv/bin/activate && python3 ~/.hermes/skills/fsi/global-market/scripts/build-fund-mapping.py

Outputs:
  - references/etf-mapping.md (main mapping table + Python code snippets)
  - references/fund-nav-history.csv (51764+ rows of historical NAV data)

Data sources:
  - Current NAV/change: fundgz.1234567.com.cn (fundgz API)
  - Historical NAV: akshare.fund_open_fund_info_em(symbol=xxx, indicator='单位净值走势')
"""

import re
import json
import akshare as ak
import pandas as pd
import requests as req
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path.home() / '.hermes' / 'skills' / 'fsi' / 'global-market'
REFERENCES_DIR = SKILL_DIR / 'references'

# ====== MASTER MAPPING: sector → list of fund items ======
# Each item: "6-digit-code + Chinese fund name"
RAW_MAPPING = {
    'CPO': ['022365永赢科技智选混合发起C'],
    '半导体': ['015968永赢半导体产业智选混合发起C'],
    '半导体材料': ['017811东方人工智能主题混合C'],
    '存储芯片': ['016874广发远见智选混合C', '025209永赢先锋半导体智选C'],
    '5G': ['002771安信新回报混合C', '022364永赢科技智选混合发起A'],
    '机器人': ['018125永赢先进制造智选混合发起C', '016531鹏华碳中和主题混合C'],
    '港股科技': ['024460华商致远回报C', '024736永赢港股通科技智选C'],
    '通信技术': ['016371信澳业绩驱动混合C', '018956中航机遇领航混合发起A'],
    '商业航天': ['015790永赢高端装备智选混合发起C'],
    '锂矿': ['012710华夏核心成长混合C', '020475中欧产业优选混合C'],
    '有色金属': ['022167富国资源精选混合发起式C', '001467华富永鑫灵活配置混合C'],
    '电网设备': ['025857华夏中证电网设备主题ETF发起式联接C', '001665平安鑫安混合C'],
    '贵金属': ['002207前海开源金银珠宝混合C'],
    '电力': ['016186广发中证全指电力ETF发起式联接C'],
    '算力租赁': ['005359东方阿尔法精选混合发起式C', '023452中欧信息科技混合发起式C'],
    '消费电子': ['018897易方达中证消费电子主题ETF发起式联接C'],
    '锂电池': ['022447前海开源周期精选混合C'],
    '白酒': ['012414招商中证白酒指数C'],
    '人工智能': ['012780博时移动互联混合C'],
    '红利低波': ['007467华泰柏瑞中证红利低波ETF联接C'],
    '黄金': ['004253国泰黄金ETF联接C', '002611博时黄金ETF联接C'],
    '新能源汽车': ['501058汇添富中证新能源汽车产业C类(LOF)'],
    '畜牧养殖': ['012725国泰中证畜牧养殖ETF发起式联接C'],
    '化工': ['020274富国中证细分化工产业ETF发起式联接C'],
    '农业': ['014064银华农业产业股票发起式C', '010770天弘中证农业主题C'],
    '银行': ['001595天弘中证银行ETF联接C'],
    '交通运输': ['012420广发价值领先混合C'],
    '港股创新药': ['015916永赢医药创新智选混合发起C'],
    '港股消费': ['010350景顺长城品质长青混合A'],
    '钢铁': ['025217永赢资源慧选混合发起式C'],
    '光伏': ['017766华夏兴和混合C'],
    '储能': ['014766中欧碳中和混合发起C'],
    '固态电池': ['014561东方汽车产业趋势混合C'],
    '稀土': ['011036嘉实中证稀土产业ETF联接C'],
    '军工': ['013566华夏军工安全混合C'],
    '煤炭': ['013275富国中证煤炭指数C'],
    '脑机接口': ['019414长城消费增值混合C'],
}


def parse_item(item):
    """'022365永赢科技智选混合发起C' → ('022365', '永赢科技智选混合发起C')"""
    return item[:6], item[6:]


def get_current_nav(code):
    """Fetch current estimated NAV via fundgz API."""
    try:
        r = req.get(f'https://fundgz.1234567.com.cn/js/{code}.js', timeout=10)
        match = re.search(r'jsonpgz\((.+?)\)\s*;?\s*$', r.text)
        if match:
            return json.loads(match.group(1))
    except Exception:
        pass
    return None


def get_history(code):
    """Fetch historical NAV via akshare."""
    try:
        return ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
    except Exception:
        return None


def compute_stats(df):
    """Compute YTD, 1w, 1m, 3m changes from historical NAV DataFrame."""
    if df is None or len(df) < 2:
        return {}
    last = df.iloc[-1]
    first = df.iloc[0]
    latest = float(last['单位净值'])

    def pct(n):
        return (float(last['单位净值']) / n - 1) * 100 if n else 0

    ytd_start = pd.Timestamp(f'{datetime.now().year}-01-01')
    ytd_df = df[df['净值日期'] >= ytd_start]
    ytd = pct(float(ytd_df.iloc[0]['单位净值'])) if len(ytd_df) >= 2 else 0

    # Recent lookback
    recent = df.tail(60)
    w1 = pct(float(recent.iloc[-5]['单位净值'])) if len(recent) >= 5 else 0
    m1 = pct(float(recent.iloc[-20]['单位净值'])) if len(recent) >= 20 else 0
    m3 = pct(float(recent.iloc[-60]['单位净值'])) if len(recent) >= 60 else 0

    return {
        'total_days': len(df),
        'start': str(first['净值日期'].date()),
        'end': str(last['净值日期'].date()),
        'latest_nav': latest,
        'ytd_chg': round(ytd, 2),
        'w1_chg': round(w1, 2),
        'm1_chg': round(m1, 2),
        'm3_chg': round(m3, 2),
    }


def build():
    # 1. Parse mapping
    all_entries = []
    for sector, items in RAW_MAPPING.items():
        for item in items:
            code, name = parse_item(item)
            all_entries.append((sector, code, name))

    print(f"Loaded {len(RAW_MAPPING)} sectors, {len(all_entries)} fund codes")

    # 2. Fetch current NAV
    print("\n=== Current NAV ===")
    current = {}
    for sector, code, name in all_entries:
        data = get_current_nav(code)
        current[code] = data
        chg = data.get('gszzl', 'N/A') if data else 'FAIL'
        print(f"  {code} ({name}): NAV={data.get('dwjz','—') if data else '—'} 预估{chg}%")
        time.sleep(0.3)

    # 3. Fetch historical NAV
    print("\n=== Historical NAV ===")
    history = {}
    all_dfs = []
    for sector, code, name in all_entries:
        df = get_history(code)
        history[code] = df
        if df is not None and len(df) > 0:
            stats = compute_stats(df)
            print(f"  {code} ({name}): {stats['total_days']}条, YTD={stats['ytd_chg']:+.2f}%")
            df['板块'] = sector
            df['基金代码'] = code
            df['基金名称'] = name
            all_dfs.append(df)
        else:
            print(f"  {code} ({name}): ❌ no data")
        time.sleep(0.5)

    # 4. Save historical CSV
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        csv_path = REFERENCES_DIR / 'fund-nav-history.csv'
        combined.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n✅ Historical CSV: {csv_path} ({len(combined)} rows)")

    # 5. Build optimized etf-mapping.md
    lines = ['# 板块主题基金映射表（优化版）']
    lines.append('')
    lines.append(f'> 基于 lof-mapping.md 的板块分类与基金代码，{datetime.now().strftime("%Y-%m-%d %H:%M")} 更新')
    lines.append('> 数据来源：天天基金净值 API (fundgz) + akshare')
    lines.append('> 历史净值统计 CSV: `references/fund-nav-history.csv`')
    lines.append('')
    lines.append('## 映射表')
    lines.append('')
    hdr = '| 板块名称 | 基金代码 | 基金名称 | 最新净值 | 日涨跌% | 近1周% | 近1月% | 近3月% | 年内% | 数据天数 |'
    lines.append(hdr)
    lines.append('|' + '|'.join(['---'] * 10) + '|')

    for sector in sorted(RAW_MAPPING):
        for item in RAW_MAPPING[sector]:
            code, name = parse_item(item)
            curr = current.get(code, {})
            hist = history[code] if code in history else None
            stats = compute_stats(hist) if hist is not None else {}

            dwjz = curr.get('dwjz') if curr else None
            gszzl = curr.get('gszzl') if curr else None
            line = f"| {sector} | {code} | {name} | {dwjz or '—'} | {f'{gszzl:+.2f}' if gszzl is not None else '—'} "
            for k in ['w1_chg', 'm1_chg', 'm3_chg', 'ytd_chg']:
                v = stats.get(k)
                line += f"| {v:+.2f}" if isinstance(v, (int, float)) else "| —"
            line += f"| {stats.get('total_days', '—')} |"
            lines.append(line)

    lines.append('')
    lines.append('## Python 查询函数（用于收盘日报）')
    lines.append('```python')
    lines.append('def query_fund_chg(code):')
    lines.append('    """通过天天基金API查询估算涨跌幅"""')
    lines.append('    import requests, re, json')
    lines.append('    try:')
    lines.append('        r = requests.get(f"https://fundgz.1234567.com.cn/js/{code}.js", timeout=10)')
    lines.append('        match = re.search(r\'jsonpgz\\((.+?)\\)\\s*;?\\s*$\', r.text)')
    lines.append('        if match:')
    lines.append('            data = json.loads(match.group(1))')
    lines.append('            return float(data.get("gszzl", 0) or 0)')
    lines.append('    except:')
    lines.append('        pass')
    lines.append('    return None')
    lines.append('```')
    lines.append('')

    outpath = REFERENCES_DIR / 'etf-mapping.md'
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n✅ etf-mapping.md written: {outpath}")


if __name__ == '__main__':
    build()
