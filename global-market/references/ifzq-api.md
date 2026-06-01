# Tencent ifzq API — A股/港股历史K线数据

> 替代被腾讯云拦截的 akshare EastMoney API。已验证对 A 股和港股均可用。

## 接口地址

```
https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},{adjust}
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| prefix | 市场前缀 | `sh`(沪) `sz`(深) `hk`(港) |
| code | 股票代码 | 6位数字(A股) / 5位数字(港股) |
| days | 请求日历天数 | 150~200（实际返回 ~150条，受限于数据存储） |
| adjust | 复权方式 | `qfq`(前复权) / `bfq`(不复权) — **仅 A 股有效** |

## 返回格式

### A 股 (qfqday 字段)

```json
{
  "code": 0,
  "data": {
    "sh600519": {
      "qfqday": [
        ["2026-01-05", "1385.000", "1426.000", "1431.880", "1385.000", "70949.000"],
        ...
      ]
    }
  }
}
```

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | 日期 | YYYY-MM-DD |
| 1 | 开盘价 | 前复权 |
| 2 | **收盘价** | 前复权 |
| 3 | 最高价 | 前复权 |
| 4 | 最低价 | 前复权 |
| 5 | 成交量 | **单位：手**（1手=100股） |

**注意**：索引顺序是 `[date, open, CLOSE, high, low, volume]` — close 在索引 2，非标准 OCHLV 顺序。

### 港股 (day 字段，无 qfqday)

```json
{
  "data": {
    "hk00700": {
      "day": [
        ["2026-01-08", "618.500", "616.000", "621.000", "610.000", "18742539.000", {corp_action_info}],
        ...
      ]
    }
  }
}
```

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | 日期 | YYYY-MM-DD |
| 1 | 开盘价 | 不复权 |
| 2 | 收盘价 | 不复权 |
| 3 | 最高价 | 不复权 |
| 4 | 最低价 | 不复权 |
| 5 | 成交量 | **单位：股**（港股按股计数） |
| 6+ | 额外信息 | 企业行动/拆合股信息（解析时忽略） |

**注意**：港股 volume 是股数，A 股 volume 是手数（100股/手）。

### 美股 (day 字段，极少返回)

```\nhttps://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usAAPL,day,,,150,qfq\n```\n\n美股数据从 2011 年起可用，但较新浪美股 API（1984年起）数据范围短。\n**优先使用新浪美股 API** 获取美股历史数据。\n\n## ⚠️ 关键陷阱：JSON 返回的 key 是 prefix+code，不是纯 code\n\nifzq 返回的 JSON 使用 `prefix + code` 作为最内层 key，而非仅 code：\n\n```json\n{\n  \"data\": {\n    \"sh600519\": {     // ← 注意：key 是 \"sh600519\"，不是 \"600519\"\n      \"qfqday\": [...]\n    }\n  }\n}\n```\n\n**正确获取方式**：\n\n```python\nfull_key = f\"{prefix}{code}\"  # 如 \"sh512890\"\nrecords = d.get(\"data\", {}).get(full_key, {}) or d.get(\"data\", {}).get(code, {})\n```\n\n错误做法（会返回 None/KeyError）：\n\n```python\n# ❌ 错误：直接用 code 查\nrecords = d[\"data\"][code]  # 不存在！\n```\n\n此规则同样适用于港股（`hk00700` 而非 `00700`）。这个陷阱在编写新的数据获取脚本时最容易踩到，因为人的直觉是用裸代码当 key。\n\n## 遗留问题

1. **datalen 上限**：即使请求 200 天，实际返回约 150~180 条记录（A 股受存储限制）。请求 150 天通常能覆盖 90 个交易日。
2. **qfqday 仅 A 股旧股/老ETF有，次新ETF和港股/美股只有`day`**：港股只有 `day`（不复权），美股也只有 `day`。A 股部分近年新上市的ETF（如 560860 工业有色ETF万家、深交所ETF）可能没有 `qfqday` 前复权数据，只有 `day`。必须 try/except 降级获取：`records = d.get('qfqday') or d.get('day')`。次新股也可能无 qfqday。
3. **网络稳定性**：腾讯云环境下工作正常，但非腾讯云环境可能存在 DNS 解析问题（如 `web.ifzq.gtimg.cn` 指向 CDN，部分海外 IP 可能被限流）。
4. **非交易时段返回最近收盘**：与 qt.gtimg.cn 行为一致。
