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
