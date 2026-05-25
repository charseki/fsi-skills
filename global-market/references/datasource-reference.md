# 数据源字段参考

## 腾讯行情 qt.gtimg.cn (A股 + 美股)

**端点**: `GET https://qt.gtimg.cn/q={prefix}{code}`

**前缀规则**:
| 市场 | 前缀 | 示例 |
|------|------|------|
| A股-上海 | `sh` | `sh600519` |
| A股-深圳 | `sz` | `sz000001` |
| 美股 | `us` | `usAAPL` |

**返回格式**: `v_{code}="field1~field2~...~fieldN"`

按 `~` 分割后的字段索引（A股和美股通用部分）：

| 索引 | 字段 | 说明 |
|------|------|------|
| 1 | name | 中文名称 |
| 2 | code | 股票代码 |
| 3 | price | 当前价格 |
| 4 | prev_close | 昨收 |
| 5 | open | 今开 |
| 6 | volume | 成交量（A股为手，美股为股） |
| 30 | datetime | 时间戳 |
| 31 | change | 涨跌额 |
| 32 | change_pct | 涨跌幅% |
| 33 | high | 当日最高 |
| 34 | low | 当日最低 |
| 35 | currency/combined | 美股=货币代码；A股=组合字段(价/手/金额) |

**A股特有字段**：
| 索引 | 字段 | 说明 |
|------|------|------|
| 35 | combined | 格式 `price/volume_hands/amount_yuan`（如 `1323.00/49661/6594983723`）|

**美股特有字段**：
| 索引 | 字段 | 说明 |
|------|------|------|
| 35 | currency | 货币代码 (USD, HKD...) |
| 37 | market_cap | 市值 (raw) |
| 39 | pe_ttm | PE (TTM) |
| 46 | en_name | 英文公司名 |
| 48 | week52_high | 52周最高 |
| 49 | week52_low | 52周最低 |

> ⚠️ A股和美股的索引差异：两者索引 1-34 布局相同（都是腾讯统一格式），但 35 之后的结构不同。

---

## 新浪行情 hq.sinajs.cn (港股)

**端点**: `GET https://hq.sinajs.cn/list=hk{code}`

**必需 Header**: `Referer: https://finance.sina.com.cn`

**返回格式**: `var hq_str_hk{code}="f0,f1,f2,...,fN"`

逗号分割字段：

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | en_name | 英文名 (如 TENCENT) |
| 1 | cn_name | 中文名 (如 腾讯控股) |
| 2 | price | 当前价 |
| 3 | prev_close | 昨收 |
| 4 | high | 最高 |
| 5 | low | 最低 |
| 6 | open | 开盘 |
| 7 | change | 涨跌额 |
| 8 | change_pct | 涨跌幅% |
| 9 | bid_price | 买入价 |
| 10 | ask_price | 卖出价 |
| 11 | turnover | 成交额 (raw value) |
| 12 | volume | 成交量 (股) |

---

## 新浪建议 suggest3.sinajs.cn (A股名称→代码)

**端点**: `GET https://suggest3.sinajs.cn/suggest/?key={name}&type=11,12&count=10`

**必需 Header**: `Referer: https://finance.sina.com.cn`

**参数说明**:
- `key`: 搜索关键词（股票名称或代码）
- `type`: 市场类型（11=上海, 12=深圳）
- `count`: 返回结果数量

**返回格式**: `var suggestvalue="NAME,MARKET_FLAG,CODE,FULL_CODE,...;"`

逗号分割字段：

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | name | 股票名称 (如 贵州茅台) |
| 1 | market_flag | 市场标识 (11=上海, 12=深圳) |
| 2 | code | 6位代码 (如 600519) |
| 3 | full_code | 完整代码 (如 sh600519) |

---

## open.er-api.com (外汇)

**端点**: `GET https://open.er-api.com/v6/latest/{base_currency}`

**特性**:
- 免费使用，无需 API key
- `{base_currency}` 为三字货币代码 (USD, EUR, CNY, JPY, GBP, HKD...)
- 默认以 USD 为基准货币
- 返回 JSON，包含 `rates` 字典和 `time_last_update_utc` 时间戳

**响应结构**:
```json
{
  "base_code": "USD",
  "rates": {
    "CNY": 6.81799,
    "EUR": 0.860568,
    "JPY": 158.758311,
    ...
  },
  "time_last_update_utc": "Mon, 18 May 2026 00:02:31 +0000"
}
```

---

## 新浪美股 API (US 指数历史)

**端点**: `GET https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_MinKService.getDailyK?symbol={sina_code}&datalen={count}`

**必需 Header**: `Referer: https://finance.sina.com.cn`

**参数说明**:
| 参数 | 说明 | 示例 |
|------|------|------|
| `symbol` | 新浪美股代码（指数加 `.` 前缀） | `.INX`, `.DJI`, `.NDX`, `.IXIC` |
| `datalen` | 返回记录数 | `60` |

**响应格式**: JSONP 包裹，解析方法：
```python
import re, json
match = re.search(r'\[.+\]', raw_response, re.DOTALL)
records = json.loads(match.group())
# 每条记录: {"d":"2026-05-18", "o":"29246.20", "h":"29250.14", "l":"28717.57", "c":"28994.37", "v":"1025998228", "a":"0"}
```

字段含义：`d`=日期, `o`=开盘, `h`=最高, `l`=最低, `c`=收盘, `v`=成交量, `a`=成交额

**指数代码映射**:
| 代码 | 新浪 symbol | 可用性 |
|------|-------------|--------|
| NDX | `.NDX` | ✅ 全历史 (2004～今, 5000+条) |
| SPX | `.INX` | ✅ 全历史 (2004～今, 5000+条) |
| DJI | `.DJI` | ✅ 全历史 (2004～今, 5000+条) |
| COMP | `.IXIC` | ✅ 全历史 (2004～今, 5000+条) |

**注意**: 数据源为东方财富 (EastMoney) 通过新浪接口提供，但不受 Tencent Cloud 拦截（因为走的是新浪域名，非直接访问 EastMoney）。

---

## 腾讯 ifzq API (web.ifzq.gtimg.cn) — A股/港股历史K线

**端点**: `GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{count},qfq`

**用途**: 获取 A 股和港股历史日 K 线数据。美股历史走新浪 US_MinKService。

**前缀规则**:

| 市场 | 前缀 | 示例 | 数据字段 | 说明 |
|------|------|------|----------|------|
| A股-上海 | `sh` | `sh600519` | `qfqday` (前复权) | ✅ 完整, 推荐 |
| A股-深圳 | `sz` | `sz002938` | `qfqday` (前复权) | ✅ 完整, 推荐 |
| 港股 | `hk` | `hk00700` | `day` (无前复权) | ✅ 完整 |

**参数说明**:
- `count`: 日历天数（非交易日数）。A 股请求 `count=150` 约得 90-100 条交易日数据
- `qfq`: 前复权参数（必须保留）

**响应格式**:
```json
{
  "code": 0,
  "msg": "",
  "data": {
    "sh600519": {
      "qfqday": [
        ["2026-01-05", "1385.000", "1426.000", "1431.880", "1385.000", "70949.000"]
        //  [0:date,     1:open,   2:close,  3:high,    4:low,     5:volume       ]
      ],
      "day": [
        ["2026-01-05", "1385.000", "1426.000", "1431.880", "1385.000", "70949.000"]
      ]
    }
  }
}
```

**字段索引** (重要!):
| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | date | 日期 `YYYY-MM-DD` |
| 1 | **open** | 开盘价 ⚠️ 注意 close 在索引2, 不是1 |
| 2 | **close** | 收盘价 |
| 3 | high | 最高价 |
| 4 | low | 最低价 |
| 5 | volume | 成交量（A股=手, 港股=股） |

**数据获取代码**:
```python
resp = _HTTP.get(
    f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    f"?param=sz002938,day,,,150,qfq",
    timeout=15
)
data = resp.json()
# A 股
records = data["data"]["sz002938"]["qfqday"]
# 港股
records = data["data"]["hk00700"]["day"]
```

**注意事项**:
- `qfqday` 仅对 A 股有效；港股数据在 `day` 字段
- `close` 在索引 2（不是索引 1），**容易混淆**
- 该 API 不支持美股个股历史 — 美股走新浪 US_MinKService
