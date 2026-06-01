# 新浪美股 API — 美股指数历史数据

替代 Nasdaq 官方 API（NDX/COMP 可用但 SPX/DJI 不可用）。新浪美股 API 在腾讯云环境下可正常访问，无需 API key。

## 端点

```
GET https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_MinKService.getDailyK?symbol={symbol}&datalen={count}
```

### 必需 HTTP Headers

```python
headers = {'Referer': 'https://finance.sina.com.cn'}
```

## 参数

| 参数 | 必需 | 说明 | 示例 |
|------|------|------|------|
| `symbol` | 是 | 美股代码（指数需加 `.` 前缀） | `.INX`, `.DJI`, `.NDX`, `.IXIC` |
| `datalen` | 是 | 返回记录数（最大约 6000+） | `60` (约3个月) |

## 响应格式

```json
// JSONP 包裹，返回格式:
var data=([{...},{...},...]);

// 每条记录:
{
  "d": "2026-05-18",     // 日期 YYYY-MM-DD
  "o": "29246.20",       // 开盘价
  "h": "29250.14",       // 最高价
  "l": "28717.57",       // 最低价
  "c": "28994.37",       // 收盘价
  "v": "1025998228",     // 成交量（股）
  "a": "0"               // 成交额（可能为0）
}
```

## ⚠️ 解析陷阱

### 1. 外层括号 `([...])`

返回数据以 `var data=([...])` 格式包裹，中间有**括号**包裹数组。直接 JSON 解析会失败：

```python
# ✅ 正确：去括号后再解析
text = r.text
idx = text.find("data=")
json_str = text[idx + 5:].strip().rstrip(";").rstrip()
if json_str.startswith("(") and json_str.endswith(")"):
    json_str = json_str[1:-1]
raw = json.loads(json_str)
```

### 2. 行格式是 dict，不是数组

每条记录是 `{"d":"...","o":"...","c":"...","h":"...","l":"...","v":"..."}` 格式的对象，**不是** `["date",open,close,high,low,volume]` 数组。

```python
# ✅ 正确：用 dict key 读取
rows.append({
    "date": row["d"],
    "open": float(row["o"]),
    "close": float(row["c"]),
    "high": float(row["h"]),
    "low": float(row["l"]),
    "volume": float(row["v"]),
})
```

```python
# ❌ 错误：按索引读数组
rows.append((row[0], row[1], row[4], ...))  # row是dict，索引报错！
```

### 3. 大量历史数据

单次请求可返回 5000+ 条记录（AAPL 从 1984 年至今约 9958 条）。务必用 `datalen` 参数控制获取量，避免内存问题。
```

## 支持的指数代码

| 代码 | 新浪 symbol | 指数 | 数据量 |
|------|-------------|------|--------|
| NDX | `.NDX` | NASDAQ-100 | 全历史 (2004至今) |
| SPX | `.INX` | S&P 500 | 全历史 (2004至今) |
| DJI | `.DJI` | Dow Jones | 全历史 (2004至今) |
| COMP | `.IXIC` | NASDAQ Composite | 全历史 (2004至今) |

## 与 Nasdaq API 的对比

| 对比项 | Nasdaq API (旧) | 新浪美股 API (当前) |
|--------|----------------|-------------------|
| NDX | ✅ | ✅ |
| COMP | ✅ | ✅ |
| SPX | ❌ "Symbol not exists" | ✅ |
| DJI | ❌ "Symbol not exists" | ✅ |
| 数据起始 | 最近60天 | 2004年至今 |
| 日期格式 | `MM/DD/YYYY` (需处理逗号) | `YYYY-MM-DD` (可直接解析) |
| 稳定性 | 偶尔返回空数据 | 稳定 (已验证 5000+ 条) |
