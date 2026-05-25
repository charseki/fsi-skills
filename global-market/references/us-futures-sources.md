# US 期货/盘前实时数据源 — 可用性记录

> 记录时间: 2026-05-22 环境: Tencent Cloud, Python 3.12, hermes-agent

## 已验证的备选数据源

### ❌ yfinance (NQ=F, NQ00Y.SG)
- 结果: `Too Many Requests. Rate limited.`
- 环境: Tencent Cloud (可能被Yahoo标记/IP段限制)
- 结论: 不可用。即使后续重试也可能继续429。

### ❌ 新浪期货 API
```python
curl -s "https://hq.sinajs.cn/list=nf_NQ00Y" -H "Referer: https://finance.sina.com.cn"
# 返回: var hq_str_nf_NQ00Y=""  (空)
curl -s "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_FutKService.getReal?symbol=MNQ00Y"
# 返回: {"__ERROR":3,"__ERRORMSG":"Service not valid"}
curl -s "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_FutKService.getFutReal?symbol=NQ00Y"
# 返回: same error
```
- 结论: 新浪不再为境外期货提供实时行情API。

### ❌ EastMoney push2 API
```python
# Secid codes tried: 86.NQ, 86.NQ00Y, 111.NQ, 111.NQ00Y, 0.137507
# All returned: {"rc":100, "data":null} — 无匹配数据
```
- 结论: 东方财富push2 API不支持海外期货品种。

### ❌ 腾讯 qt.gtimg.cn 期货查询
```python
curl -s "https://qt.gtimg.cn/q=usNQ"     # 返回网秦(NQ Mobile)股票, 非NQ期货
curl -s "https://qt.gtimg.cn/q=usMNQ"    # v_pv_none_match
curl -s "https://qt.gtimg.cn/q=usNQH26"  # v_pv_none_match
curl -s "https://qt.gtimg.cn/q=usNQ00Y"  # v_pv_none_match
curl -s "https://qt.gtimg.cn/q=us@NQ.0"  # v_pv_none_match
curl -s "https://qt.gtimg.cn/q=usES"     # 返回Eversource Energy股票, 非ES期货
```
- `us` 前缀在腾讯行情中表示美股**股票/ETF/指数**，不覆盖CME期货。
- `usNQ` → 网秦(NQ Mobile, 中概股)，`usES` → Eversource Energy (公用事业股)
- CME期货代码(NQ, ES, YM, RTY等)与美股股票代码冲突。

### ❌ Google Finance
- `NQ=COMEX` 页面在无头Chrome中无法渲染（网络限制）
- `--no-sandbox` 修复Chrome启动问题但Google页面仍超时
- 不建议继续尝试，这是一个持续性的环境限制

### ❌ Investing.com / MarketWatch / CNBC
- 依赖Chrome无头浏览器渲染
- Chrome需要 `--no-sandbox` 标志（Ubuntu 23.10+ AppArmor限制）
- 即使 `--no-sandbox`，多个金融网站也超时（可能是网络限制）

## 实测可用的数据

### ✅ 腾讯 qt.gtimg.cn US指数快照
```python
# NDX (Nasdaq 100)
curl -s "https://qt.gtimg.cn/q=usNDX" | iconv -f GBK -t UTF-8
# 字段: 名称~.NDX~当前价~昨收~今开~成交量~...~时间戳~涨跌额~涨跌幅~最高~最低~货币

# SPX (S&P 500)
curl -s "https://qt.gtimg.cn/q=usINX" | iconv -f GBK -t UTF-8

# DJI (Dow Jones)
curl -s "https://qt.gtimg.cn/q=us.DJI" | iconv -f GBK -t UTF-8
```
- **局限**：只返回常规交易时段数据，非实时盘前/盘后数据
- 时间戳(字段30)在US指数中似乎使用北京时间记录
- 数据更新频率：约每4-5分钟（见usNDX在11:36→11:40间更新）

### ✅ 新浪美股 K线历史
```python
# 日K线 (2004至今)
url = 'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20data=/US_MinKService.getDailyK?symbol=.INX&datalen=60'
headers = {'Referer': 'https://finance.sina.com.cn'}
```
- 数据到最近的收盘日为止
- 盘前查询返回最近收盘日的数据
- 支持 NDX(.NDX), SPX(.INX), DJI(.DJI), COMP(.IXIC)

## 总结

| 数据需求 | 可行性 | 推荐方案 |
|---------|--------|---------|
| US指数（常规交易时段） | ✅ | 腾讯 qt.gtimg.cn |
| US个股（常规交易时段） | ✅ | 腾讯 qt.gtimg.cn |
| US指数历史 K线 | ✅ | 新浪美股 API |
| **US指数盘前/盘后** | ❌ | 无可用数据源，提供最近收盘价 |
| **NQ/ES期货实时** | ❌ | 无可用数据源 |
| **US个股盘前/盘后** | ❌ | 无可用数据源 |
| **经济数据/宏观日历** | ⚠️ | 可尝试百度搜索结果 |
