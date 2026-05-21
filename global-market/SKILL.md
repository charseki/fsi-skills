---
name: global-market
description: 全球金融市场速查 + A股板块行情，支持 A 股、美股、港股、外汇、概念/行业板块，自动识别市场并路由到对应数据源
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, market-data, fsi, stock]
    category: fsi
    requires_toolsets: [terminal, file]
---

# 全球市场速查

## When to Use
- 用户查询任何股票、基金（代码）、货币的行情
- 用户说"查一下 XXX"、"XXX 行情"、"XXX 最新价"、"看看 XX"
- 用户说"全球市场"查看概览
- 用户输入股票代码（A股6位、美股字母、港股5位）、基金代码（6位，如016814）或外汇关键词
- 用户查询批量**板块/行业/概念**涨跌幅（如"帮我查下CPO、机器人、有色金属这几个板块"）

## Procedure

1. 接收用户查询关键词（股票名称、代码、基金代码、外汇关键词，或逗号分隔批量查询）
2. 执行脚本自动识别市场类型并返回行情：

   ```bash
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py "<查询内容>"
   ```

3. 直接打印脚本标准输出 — 已格式化含 emoji 表情符号，无需额外处理
4. 如果脚本返回 `❌` 开头，说明查询失败

**批量查询**：逗号分隔多个查询，如：

   ```bash
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py "茅台,AAPL,00700"
   ```

**指数历史分析**：查询美股指数近一个月走势（通过新浪美股 API）：

   ```bash
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history NDX
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history SPX
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history DJI
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history COMP
   ```

   支持全部4个主要美股指数：NDX（NASDAQ-100）、SPX（S&P 500）、DJI（道琼斯）、COMP（NASDAQ Composite）。

**生成K线走势图**：在指数历史分析基础上增加 matplotlib 暗色主题K线图（含5日/20日均线、成交量柱）：

   ```bash
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history SPX --chart
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --history NDX --chart
   ```

   输出：文字分析 + 图片路径 `/tmp/hermes_index_chart.png`（132KB, 150dpi）。

**板块查询**：查询 A 股概念/行业板块涨跌幅（通过同花顺资金流向 + 新浪行业数据）：

   ```bash
   # 查询特定概念板块（逗号分隔）
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --sector "CPO,机器人,存储芯片"

   # 模糊匹配
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --sector 半导体

   # 所有概念板块排行（按涨跌幅降序）
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --sector all

   # 所有行业板块排行
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --sector all --industry

   # 板块速览（涨跌前 5）
   ~/venv/bin/python3 ~/.hermes/skills/fsi/global-market/scripts/run.py --sector all --top5
   ```

**基金代码兜底**（v1.0.0 自动处理）：6 位纯数字输入 → 先查 A 股 → 若 A 股无此代码 → 自动尝试天天基金净值 API。无需手动区分基金代码。

**CSI 中证指数兜底**：如果查询代码以 H 开头（如 H30269），且脚本返回 ❌，则走 CSI 指数兜底流程（参见下方【CSI 中证指数查询】章节）。

### 数据流示意

```
用户输入 "016814"
  → detect_market() → market="a", identifier="016814"
  → query_a_stock("016814") → sh/sz 都返回无匹配
  → 自动调用 query_fund("016814") → 天天基金 API ✅
  → 返回格式化基金行情

用户输入 "茅台,AAPL,00700"
  → detect_market() 对每个输入判断
  → batch_query() 并行（实际串行）查询各市场
  → 分割线分隔结果
```

## 市场自动识别

脚本 `scripts/run.py` 中的 `detect_market()` 按以下优先级判断市场类型：

| 优先级 | 市场 | 匹配规则 | 示例 |
|--------|------|----------|------|
| 1 (最高) | 外汇 (fx) | 含「汇率」「美元」「欧元」「USD」「CNY」等关键词 | "汇率美元", "USD/CNY", "美元兑欧元" |
| 2 | 港股 (hk) | 5位纯数字 或 `.HK` 后缀 | "00700", "00700.HK" |
| 3 | 美股/指数 (us) | 1-5位纯英文字母（排除 SH/SZ/HSI） | "AAPL", "NDX", "SPX", "DJI" |
| 4 | CSI 中证指数 (csi) | 6位以上字母数字混合，以字母开头（如 H30269）| "H30269", "H00973" |
| 5 (兜底) | A股 (a) | 中文名称、6位纯数字代码或任何其他输入 | "茅台", "600519" |

**注意**：美股指数（NDX、SPX、DJI）走腾讯行情快照，显示当前价和涨跌幅。如需深度历史分析（周涨跌幅、最大回撤），使用 `--history NDX` 模式。A股名称搜索通过新浪建议接口（suggest3.sinajs.cn）转换为代码后再查行情。

**CSI 中证指数（H-series）**：此类指数代码以 H 开头（如 H30269 中证红利低波），不在腾讯 qt.gtimg.cn 或新浪 hq.sinajs.cn 的覆盖范围内。参见下方【CSI 中证指数查询】章节获取兜底方案。

### 指数代码支持详情

| 代码 | 指数名称 | 快照查询 | 历史分析 (`--history`) | K线图 (`--chart`) |
|------|----------|----------|----------------------|-------------------|
| NDX | NASDAQ-100 | ✅ 腾讯行情 usNDX | ✅ 新浪美股 API | ✅ matplotlib |
| SPX | S&P 500 | ✅ 腾讯映射 usINX | ✅ 新浪美股 API (.INX) | ✅ matplotlib |
| DJI | Dow Jones | ✅ 腾讯映射 us.DJI | ✅ 新浪美股 API (.DJI) | ✅ matplotlib |
| COMP | NASDAQ Composite | ❌（与 Compass 股票冲突） | ✅ 新浪美股 API (.IXIC) | ✅ matplotlib |

## 天天基金净值 API (fundgz.1234567.com.cn) 字段

> 脚本 v1.0.0+ 已内置此兜底逻辑，6位数字输入自动尝试。以下为参考字段说明。

格式：`jsonpgz({"fundcode":"...","name":"...","jzrq":"...","dwjz":"...","gsz":"...","gszzl":"...","gztime":"..."})`

**注意**：`gsz` / `gszzl` 是盘中估算值，不是官方净值。官方净值（`dwjz`）在交易日收盘后公布。

## 数据源

| 市场 | 数据源 | 接口 | 依赖 |
|------|--------|------|------|
| **A股** | 腾讯行情 | `qt.gtimg.cn/q=sh{code}` / `q=sz{code}` | requests (无需 akshare) |
| **基金** | 天天基金 | `fundgz.1234567.com.cn/js/{code}.js` | requests（脚本内置兜底） |
| **美股** | 腾讯行情 | `qt.gtimg.cn/q=us{symbol}` | requests (无需 yfinance) |
| **港股** | 新浪行情 | `hq.sinajs.cn/list=hk{code}` (需 Referer header) | requests |
| **外汇** | open.er-api.com | `GET /v6/latest/{base}` | requests |
| **A股名称→代码** | 新浪建议 | `suggest3.sinajs.cn/suggest/?key={name}&type=11,12` | requests |
| **CSI H-series** | 天天基金 | `fundgz.1234567.com.cn/js/{code}.js`（通过跟踪基金推算） | requests |
| **证券名称→代码** | Tencent smartbox | `smartbox.gtimg.cn/s3/?v=2&q={name}&t=all`（返回 GBK 编码） | curl + iconv |
| **指数历史** | 新浪美股 | `stock.finance.sina.com.cn/usstock/api/...`（需 Referer） | requests |

**只依赖 `requests` 一个 pip 包。** akshare 和 yfinance 在部分云环境（特别是腾讯云）可能被拦截/限流。

## 腾讯行情 (qt.gtimg.cn) 字段索引

数据返回格式：`v_{code}="field1~field2~...~fieldN"`，按 `~` 分割。

### A股 (sh/sz 前缀)

| 索引 | 字段 | 示例 |
|------|------|------|
| 1 | 名称 | 贵州茅台 |
| 2 | 代码 | 600519 |
| 3 | 当前价 | 1323.00 |
| 4 | 昨收 | 1332.95 |
| 5 | 今开 | 1336.00 |
| 6 | 成交量(手) | 49661 |
| 31 | 涨跌额 | -9.95 |
| 32 | 涨跌幅% | -0.75 |
| 33 | 最高 | 1342.68 |
| 34 | 最低 | 1319.61 |
| 35 | 组合字段(价/手数/金额) | 1323.00/49661/6594983723 |

### 美股 (us 前缀)

| 索引 | 字段 | 示例 |
|------|------|------|
| 1 | 中文名 | 苹果 |
| 2 | 代码 | AAPL.OQ |
| 3 | 当前价 | 300.23 |
| 4 | 昨收 | 298.21 |
| 5 | 今开 | 297.90 |
| 30 | 时间戳 | 2026-05-15 16:00:02 |
| 31 | 涨跌额 | 2.02 |
| 32 | 涨跌幅% | 0.68 |
| 33 | 最高 | 303.20 |
| 34 | 最低 | 296.52 |
| 35 | 货币 | USD |
| 39 | PE(TTM) | 36.35 |
| 46 | 英文名 | Apple Inc. |
| 48 | 52周最高 | 303.20 |
| 49 | 52周最低 | 192.71 |

A股和美股关键区别：**A股涨跌幅/最高/最低在索引 31-34，美股在索引 31-34 相同**，但 PE 和 52周范围位置不同。

## 新浪港股 (hq.sinajs.cn) 字段索引

格式：`var hq_str_hk{code}="EN_NAME,CN_NAME,PRICE,PREV_CLOSE,HIGH,LOW,OPEN,CHANGE,CHG_PCT,..."`

| 逗号索引 | 字段 | 示例 |
|----------|------|------|
| 0 | 英文名 | TENCENT |
| 1 | 中文名 | 腾讯控股 |
| 2 | 当前价 | 449.400 |
| 3 | 昨收 | 456.400 |
| 4 | 最高 | 457.800 |
| 5 | 最低 | 445.800 |
| 6 | 开盘 | 449.400 |
| 7 | 涨跌额 | -7.000 |
| 8 | 涨跌幅% | -1.534 |
| 11 | 成交额 | 12499006721 |
| 12 | 成交量 | 27772376 |

**注意**：新浪港股 API 需要 `Referer: https://finance.sina.com.cn` HTTP header，否则返回空。

## 外汇格式支持

支持以下查询格式：

- `汇率美元` → USD→CNY
- `美元兑欧元` → USD→EUR
- `USD/CNY` → USD→CNY
- `USD to JPY` → USD→JPY

如果 base 和 target 相同（如"汇率美元"只匹配到 target=USD 但 base 也是 USD），自动 fallback target 为 CNY。

## Common Pitfalls

1. **akshare/yfinance 在腾讯云环境不可用**：Tencent Cloud 拦截 EastMoney API，Yahoo Finance 返回 429。脚本已内置替代数据源（qt.gtimg.cn + hq.sinajs.cn），直接使用 `requests` 无需安装 akshare/yfinance。
2. **新浪港股需要 Referer header**：不加返回空数据。必须在请求头设置 `Referer: https://finance.sina.com.cn`。
3. **新浪港股成交额在索引 11 (raw value)，不是索引 12**：容易混淆，成交量在 12。
4. **美股 52周范围数据来自腾讯字段 48/49（不是 43/44）**：腾讯原始数据中 43/44 是股指参考值，不是个股的 52周范围。
5. **A股名称搜索依赖新浪建议 API**：`suggest3.sinajs.cn` 偶尔不稳定，如果名称搜索失败可以提示用户使用 6 位代码查询。
6. **港股代码需要 5 位带前导零**：00700 而非 700，脚本自动 `zfill(5)` 处理。
7. **外汇 API 免费但有调用次数限制**：open.er-api.com 无认证免费使用，但频繁调用可能限流。
8. **超出交易时间的行情数据**：返回的是最近收盘价，用户可能误以为是实时价。
9. **基金代码（6位以0/01开头）会被误判为 A 股代码**：脚本默认把 6 位数字路由到 A 股，而基金 6 位代码（如 016814）在腾讯行情查不到，返回 ❌。v1.0.0 已内置自动基金兜底，不再需要手动指定。
10. **指数全名（如"NASDAQ-100"）不被识别**：只能识别短代码（NDX）、6位数字或中文名称。用户输入"NASDAQ-100"会落入 A 股兜底失败。如果用户输入指数全名，提示使用标准代码（NDX、SPX、DJI 等）。
11. **美股夜盘（盘后）数据不可用**：腾讯行情 qt.gtimg.cn 只返回常规交易时段数据。盘后/夜盘价格不在字段中。如需盘后数据，应让用户等到常规交易收盘后（北京时间凌晨4点后）再查询。
12. **6位数字输入自动走基金兜底**：如 016814 先查 sh/sz 都失败后自动查天天基金，无需用户手动指定"基金"关键词。
13. **指数代码（NDX/SPX/DJI）走腾讯行情快照而非历史分析**：直接输入 NDX 返回的是腾讯行情快照（当前价），历史分析需用 `--history NDX` 模式。目前全部4个指数（NDX/SPX/DJI/COMP）均支持历史分析。
14. **批量查询一次最多 5-6 个**：每个查询串行执行，太多会导致总超时。超过 6 个建议分批查。
15. **COMP 不是纳斯达克综合指数**：直接输入 COMP 会查腾讯行情，但返回的是 Compass 股票而非纳斯达克综合指数。查合成指数需用 `--history COMP`。
16. **--chart 依赖 matplotlib + numpy**：这两个包已安装在 `~/venv/` 中。如果将来重装环境，需 `~/venv/bin/pip install matplotlib numpy`。
17. **CSI 中证指数（H-series）不在腾讯/新浪/东方财富标准 API 中**：代码如 H30269 在所有常用接口均不可直接查询，必须走跟踪基金兜底方案。参见【CSI 中证指数查询】章节。
18. **腾讯 smartbox 返回 GBK 编码**：`smartbox.gtimg.cn/s3/` 返回 GBK 编码的文本。需用 `iconv -f GBK -t UTF-8` 转码。参数 `t=all` 返回所有类型（股票/ETF/基金/指数），`t=zs` 只返回指数。
19. **smartbox 搜索用中文名而非代码**：smartbox 使用中文关键词搜索（如"红利低波"），不直接支持 CSI 代码查询。结果格式为 `市场~代码~名称~拼音缩写~类型` 的串联，可用 `^` 分割解析。
20. **CSI 指数涨跌幅为推算值，非精确值**：通过基金 `gszzl` 字段推算的指数涨跌幅可能存在 ±0.05% 的误差。ETF 实时价（如 512890）是市场交易价，也不等于指数精确值。

## Verification Checklist

- [ ] 输入 A 股名称（如"茅台"、"中国平安"）返回正确行情
- [ ] 输入 A 股代码（如"600519"）返回正确行情
- [ ] 输入美股代码（如"AAPL"、"GOOGL"）返回行情 + PE + 52周范围
- [ ] 输入港股代码（如"00700"、"00388"）返回行情 + 成交额
- [ ] 输入外汇关键词（如"汇率美元"、"USD/CNY"、"美元兑欧元"）返回汇率
- [ ] 输入基金代码（如"016814"）自动兜底返回净值 + 估算涨跌幅
- [ ] 批量查询（如"茅台,AAPL,00700"）用分割线分隔各结果
- [ ] 指数历史（`--history NDX`）返回周涨跌幅 + 最大回撤 + 区间振幅
- [ ] K线图（`--history SPX --chart`）生成 matplotlib 图片
- [ ] CSI 中证指数（如 H30269）走跟踪基金兜底，返回指数估算涨跌幅
- [ ] `--sector "CPO,机器人"` 返回概念板块涨跌幅
- [ ] `--sector all` 列出所有概念板块
- [ ] `--sector all --industry` 列出所有行业板块
- [ ] `--sector all --top5` 显示涨跌前5名
- [ ] `--sector 半导体` 模糊匹配到 "第三代半导体"
- [ ] 输入未知代码（如"XXXX"）返回友好错误提示

## 美股指数历史行情分析 (--history)

当用户需要美股指数的**周涨幅、回撤、历史走势**时，使用 `--history` 模式调用新浪美股 API。

**支持指数**：NDX（NASDAQ-100）、SPX（S&P 500）、DJI（道琼斯）、COMP（NASDAQ Composite）。
**数据源**：新浪美股 `stock.finance.sina.com.cn/usstock/api/jsonp.php`（需 Referer header）。
**数据范围**：2004 年至今，脚本自动截取最近约 30 个交易日。

### 数据获取

```python
import requests
from datetime import datetime, timedelta

url = 'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_MinKService.getDailyK?symbol=.INX&datalen=60'
headers = {'Referer': 'https://finance.sina.com.cn'}
r = requests.get(url, headers=headers, timeout=15)
# 提取 JSON 数组并解析
```

### 关键指标计算

| 指标 | 公式 |
|------|------|
| **区间涨跌幅** | `(last_close / first_close - 1) * 100` |
| **近一周涨跌幅** | `(last_close / close_5_trading_days_ago - 1) * 100` |
| **最大回撤 (MDD)** | 遍历每日收盘价，`min((close - peak) / peak * 100)` |
| **日内最大振幅** | `max((high - low) / close * 100)` |

### 响应逻辑

- 返回格式化表格 + 文字总结（周涨跌幅、周内最高最低、最大回撤数值及发生日期）
- 数据截至最近交易日（美股盘前查询返回上一交易日数据）

### 注意

- 新浪美股 API 支持全部4个主要指数（NDX, SPX, DJI, COMP），数据从 2004 年至今
- 个股历史使用腾讯 qt.gtimg.cn 只返回当前快照，无历史 K 线

## A股板块查询 (--sector)

### When to Use
- 用户问「今天哪些板块涨了」「XX 板块行情」「看看板块排名」
- 用户说「帮我分析下 XX、YY、ZZ 这几个板块今日表现」
- 需要批量查询 5-30 个板块涨跌幅
- 查看市场整体情绪（普涨/普跌/分化）

### 用法

```bash
# 查询特定概念板块（精确/模糊匹配）
~/venv/bin/python3 run.py --sector "CPO,机器人,存储芯片"
~/venv/bin/python3 run.py --sector 半导体        # 模糊匹配 "第三代半导体"
~/venv/bin/python3 run.py --sector 人工智能

# 列出所有概念板块（按涨跌幅降序排列）
~/venv/bin/python3 run.py --sector all

# 行业板块查询
~/venv/bin/python3 run.py --sector "有色金属,电力,房地产" --industry
~/venv/bin/python3 run.py --sector all --industry    # 列出所有行业板块

# 快速概览（涨跌前5名）
~/venv/bin/python3 run.py --sector all --top5
~/venv/bin/python3 run.py --sector all --top10       # 自定义显示数量
```

### 数据流示意

```
用户输入 --sector "CPO,机器人,存储芯片"
  → _load_concept_flow()  # 优先同花顺资金流向概念（387个，最全）
  → 逐个匹配：精确→模糊
  → CPO → 共封装光学(CPO): -4.61%
  → 机器人 → 机器人概念: -2.50% + 人形机器人: -1.56% (多匹配)
  → 存储芯片 → 存储芯片: -5.28%
  → 输出格式化结果

用户输入 --sector all
  → 获取全部概念数据
  → 按涨跌幅降序排序
  → 输出完整列表
```

### 模糊匹配规则

| 用户输入 | 匹配结果 | 说明 |
|----------|----------|------|
| `半导体` | ≈ 第三代半导体 (-4.76%) | 无\"半导体\"独立概念，匹配到最相关 |
| `红利低波` | ≈ 高股息精选 (-1.34%) | 无\"红利低波\"概念，匹配到最接近 |
| `5G` | → 5G (-3.95%) | 精确匹配 |
| `汽车` | → 华为汽车、新能源汽车、汽车电子...（多匹配） | 关键词匹配到多个相关板块 |

### 数据源

| 数据源 | 覆盖范围 | 函数 | 涨跌幅字段 | 环境限制 |
|------|----------|------|-----------|---------|
| **同花顺 概念资金流向**（首选） | 387 个概念 | `ak.stock_fund_flow_concept()` | `行业-涨跌幅` | ✅ Tencent Cloud 可用 |
| **新浪 概念板块行情**（备选） | 175 个概念 | `ak.stock_sector_spot(indicator='概念')` | `涨跌幅` | ✅ Tencent Cloud 可用 |
| **新浪 行业板块** | ~49 个行业 | `ak.stock_sector_spot(indicator='新浪行业')` | `涨跌幅` | ✅ Tencent Cloud 可用 |
| ❌ **东方财富**（禁用） | — | `stock_board_*_em` | — | ❌ Tencent Cloud 拦截 |

脚本自动优先使用同花顺资金流向数据（387个概念，更全），失败时回退到新浪数据。

### 常见板块名称映射

| 用户习惯说 | 数据源中实际名称 | 类型 |
|------------|------------------|------|
| CPO | 共封装光学(CPO) | 概念 |
| 存储芯片 | 存储芯片 | 概念 |
| 机器人 | 机器人概念 / 人形机器人 | 概念 |
| 半导体 | 第三代半导体 / 芯片概念 | 概念 |
| 黄金 | 黄金概念 | 概念 |
| 稀土 | 稀土永磁 | 概念 |
| 光伏 | 光伏概念 | 概念 |
| 锂电池 | 锂电池概念 | 概念 |
| 煤炭 | 煤炭概念 | 概念 |
| 红利低波 | 高股息精选（最接近） | 概念 |
| 贵金属 | 黄金概念（最接近） | 概念 |
| 有色金属 | 有色金属（行业） | 行业 |
| 电力 | 电力行业（行业） | 行业 |
| 房地产 | 房地产（行业） | 行业 |
| 医疗 | 医疗器械（行业）/ 医疗器械概念 | 行业/概念 |
| 汽车 | 汽车制造（行业）/ 华为汽车（概念） | 行业/概念 |

### 快速概览（--top）

```bash
# 涨跌幅前5
~/venv/bin/python3 run.py --sector all --top5
```

输出示例：
```
📊 A股概念板块速览（共 387 个）

🔺 涨幅前 5：
  ➡️ 减速器: -0.37%
  ➡️ 电子纸: -0.62%
  ➡️ 华为汽车: -1.07%
  ➡️ 毛发医疗: -1.17%
  ➡️ 芬太尼: -1.17%

🔻 跌幅前 5：
  📉 F5G概念: -5.97%
  📉 国家大基金持股: -5.75%
  📉 存储芯片: -5.28%
  📉 铜缆高速连接: -5.24%
  📉 光刻机: -5.17%
```

### 批量查询流程（Hermes Agent 使用）

当用户给出 10+ 个板块名称时的推荐做法 — 一次性获取全部数据然后在内存中匹配，避免重复调用：

```python
import akshare as ak

# 一次性获取所有数据
concept = ak.stock_fund_flow_concept()    # 387 个概念
industry = ak.stock_sector_spot(indicator='新浪行业')  # 49 个行业

# 构建查找字典
concept_dict = {row['行业']: row['行业-涨跌幅'] for _, row in concept.iterrows()}
industry_dict = {row['板块']: row['涨跌幅'] for _, row in industry.iterrows()}

# 对每个用户输入逐一匹配
sectors = ['CPO', '机器人', '有色金属', ...]  # 用户输入
results = {}
for s in sectors:
    # 精确 → 部分 → 行业 → 近似
    ...
```

### Common Pitfalls

1. **不要使用 East Money API**：`stock_board_concept_spot_em()` 在 Tencent Cloud 返回空，必须使用同花顺或新浪数据源。
2. **港股板块无数据**：A 股数据源没有港股板块指数（如\"港股创新药\"），如需查询可查港股个股。
3. **概念/行业分类差异**：同一主题可能以不同名称存在于概念板块和行业板块（如\"煤炭概念\" vs \"煤炭行业\"），涨跌幅可能不同。概念板块更细分，行业板块更综合。
4. **名称不完全匹配**：用户输入的板块名称常与数据源中的精确名称不同（如\"红利低波\"→\"高股息精选\"），脚本已内置模糊匹配。
5. **涨幅数值差异**：`fund_flow_concept()` 和 `sector_spot(indicator='概念')` 对同一概念的涨跌幅数值可能有 0.5-2% 的差异，因为计算口径不同（资金流向 vs 新浪自算）。脚本优先使用 `fund_flow_concept()`。
6. **数据非实时（约15分钟延迟）**：这两路数据源均非 Level-2 实时数据，与交易所官方收盘数据可能有微小偏差。
7. **scope 越大越慢**：每次调用 `fund_flow_concept()` 约需 1-3 秒（内部爬取多个分页），批量查询时只需调用一次然后内存中匹配。
8. **--sector 会拖慢首次使用（加载 akshare）**：第一次调用因为 pandas/akshare 导入延迟约 3-5 秒，之后同进程内再调用会快很多。
9. **概念板块总数波动**：同花顺概念板块数量随时间增减（当前约 387 个），不是固定值。

## CSI 中证指数查询

CSI（中证）指数的代码以 H 开头（如 H30269 中证红利低波动指数），这类指数**不在**以下常见数据源中：
- ❌ 腾讯 qt.gtimg.cn（返回 `v_pv_none_match`）
- ❌ 新浪 hq.sinajs.cn（返回空字符串）
- ❌ 东方财富 push2 API（腾讯云环境被拦截）
- ❌ 中证官网 csindex.com.cn（Vue SPA，需 JavaScript 渲染）

### 兜底方案：通过跟踪基金推算

**原理**：CSI 指数有对应的 ETF 和 ETF 联接基金，这些基金的净值变动≈指数涨跌幅。天天基金 API（fundgz.1234567.com.cn）不受腾讯云环境限制。

**步骤**：

1. **查名 → 找关联 ETF/基金**：用腾讯 smartbox 搜索中文名，找到跟踪该指数的基金代码：

   ```bash
   # 搜索中文名获取相关证券
   curl -s "https://smartbox.gtimg.cn/s3/?v=2&q=红利低波&t=all" | iconv -f GBK -t UTF-8
   ```

   返回结果中 `^jj~` 为基金，`^ETF` 为 ETF。如 红利低波 的 smartbox 结果包含基金代码 007466（华泰柏瑞中证红利低波ETF联接A）。

2. **查天天基金 API 获取估算涨跌幅**：

   ```bash
   curl -s "https://fundgz.1234567.com.cn/js/{基金代码}.js"
   ```

   返回 `jsonpgz({"gszzl":"0.66",...})` 中 `gszzl` 为估算涨跌幅百分比。该估算值基于跟踪指数的波动计算，可近似视为指数今日涨跌幅。

3. **查 ETF 实时价**：如果找到对应 ETF（如 512890 红利低波ETF华泰柏瑞），可通过腾讯行情获取实时价：

   ```bash
   curl -s "https://qt.gtimg.cn/q=sh{etf代码}" | iconv -f GBK -t UTF-8
   ```

### 已知 CSI 指数 → 跟踪基金映射

| CSI 代码 | 指数名称 | 跟踪 ETF | 跟踪联接基金 |
|----------|----------|----------|------------|
| H30269 | 中证红利低波动 | 512890 (华泰柏瑞) | 007466 (A类) / 007467 (C类) |
| H30269 | 中证红利低波动 | 563020 (易方达) | 020602 (发起式A) |
| H30269 | 中证红利低波动100 | 515100 (景顺长城) / 515450 (南方) | 008114/008115 (天弘联接) |
| 000922 | 中证红利 | — (可用腾讯 `s_sh000922` 直接查) | — |

**所有 CSI H-series 指数**的 query 流程统一走此兜底。smartbox 搜索不到时（如冷门指数），告知用户目前 API 限制。

### 示例：查询 H30269 今日涨跌幅

```bash
# 1. 找到跟踪基金
curl -s "https://smartbox.gtimg.cn/s3/?v=2&q=红利低波&t=all" | iconv -f GBK -t UTF-8
# 输出: ...^jj~007466~华泰柏瑞中证红利低波ETF联接A~...

# 2. 查基金估算涨跌幅
curl -s "https://fundgz.1234567.com.cn/js/007466.js"
# 输出: jsonpgz({"gszzl":"0.66",...}) → 今日预估 +0.66%

# 3. 也可查 ETF 实时价
curl -s "https://qt.gtimg.cn/q=sh512890" | iconv -f GBK -t UTF-8
# → 红利低波ETF当前价 1.169，涨幅 +0.78%
```

### 局限

- **估算不是精确值**：基金 `gsz` 是盘中估算值，与指数实际值可能有微小偏差（通常 <0.05%）
- **非交易日无数据**：周末和节假日天天基金不提供估算值
- **冷门指数可能无跟踪基金**：部分冷门 CSI 指数没有对应的公开 ETF/联接基金
- **每天首次查**：smartbox 结果稳定，key 映射（指数→基金代码）可在首次查询后存入记忆复用

<!-- 板块/行业行情查询旧章节已合并到上方 ## A股板块查询 (--sector) -->

## References

- `references/csi-indices.md` — CSI H-series 中证指数数据来源与映射表细化
- `references/sector-mapping.md` — 28个常见 A 股板块/行业名称映射表（用户输入→数据源精确名）
- `references/datasource-reference.md` — 各数据源字段详解
- `references/nasdaq-api.md` — 新浪美股 API 文档（指数历史数据，替代 Nasdaq API）
- `references/fund-api.md` — 天天基金净值 API（基金实时估算净值）
- `references/charting.md` — matplotlib 暗色主题 K 线图生成（含 --chart 自动化用法）
