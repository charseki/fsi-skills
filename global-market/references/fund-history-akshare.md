# 基金历史净值 — akshare 批量采集 (fund_open_fund_info_em)

## 接口

```python
import akshare as ak

# 获取基金历史单位净值走势
df = ak.fund_open_fund_info_em(
    symbol="022365",       # 6位基金代码
    indicator="单位净值走势"  # 固定参数
)
```

## 返回值

| 列名 | 含义 | 类型 | 示例 |
|------|------|------|------|
| 净值日期 | 交易日 | str (YYYY-MM-DD) | 2026-05-25 |
| 单位净值 | 当日单位净值 | float | 5.7114 |
| 日增长率 | 当日涨跌幅 (%) | float | 4.44 |

## 环境验证

| 环境 | 状态 | 说明 |
|------|------|------|
| **Tencent Cloud** | ✅ 可用 | 少数能在腾讯云工作的 EastMoney 后端 API |
| 本地开发机 | ✅ 可用 | 无特殊限制 |
| GitHub Codespaces | ⚠️ 可能 | 取决于网络出口 |

## 在 run.py 中的使用

已封装为 `_fetch_fund_nav_history(code, days=120)`：

```python
def _fetch_fund_nav_history(code, days=120):
    import akshare as ak
    df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
    if df is None or df.empty:
        return None

    parsed = []
    for _, row in df.iterrows():
        dt = datetime.strptime(str(row['净值日期']), '%Y-%m-%d')
        nav = float(row['单位净值'])
        parsed.append({'date': dt, 'nav': nav})

    parsed.sort(key=lambda x: x['date'])
    if len(parsed) > days:
        parsed = parsed[-days:]
    return parsed
```

返回按日期正序排列的 list[dict]，用于回撤计算（HC）、相关性分析、最大回撤分布等。

## 性能特征

| 指标 | 值 |
|------|-----|
| 首次调用延迟 | ~2-3 秒（pandas + akshare lazy-load） |
| 同进程后续调用 | ~0.5-1 秒 / 次（数据已缓存） |
| 连续调用限流 | 建议 `time.sleep(0.5)` 间隔，避免连接池超载 |
| 数据范围 | 成立以来全部净值，通常 500-2000+ 条 |

## 其他可用 indicator 参数

| indicator | 说明 |
|-----------|------|
| `单位净值走势` | ✅ 最常用，日频净值 + 日增长率 |
| `累计收益率走势` | 成立以来累计收益率曲线数据 |
| `单位累计净值` | 单位净值 + 累计净值（含分红再投） |

## 与 fundgz API 的区别

| 维度 | fundgz (fund-api.md) | akshare fund_open_fund_info_em |
|------|----------------------|-------------------------------|
| 数据 | 当日盘中估算净值 | 全量历史官方净值 |
| 实时性 | ✅ 盘中实时 (gsz) | ❌ T+1（官方数据） |
| 批量 | 单只 (每次) | 单只 (每次) |
| 反爬 | 轻 (JSONP) | 中等 (EastMoney 后端) |
| 腾讯云 | ✅ 可用 | ✅ 可用 |

## Common Pitfalls

1. **首次延迟**：首次调用约 2-3 秒，因 akshare 需加载 pandas，不建议在延迟敏感场景中依赖。
2. **新基金数据不足**：成立不足 1 个月的基金可能只有 3-5 条数据，无法做有意义的回撤分析。
3. **LOF/ETF联接 vs 场内ETF**：此 API 返回的是**基金净值**，非场内 ETF 交易价。LOF 联接基金的净值和场内 ETF 成交价可能不同。
4. **历史数据非实时追加**：`fund-nav-history.csv` 的静态快照需重新运行 `build-fund-mapping.py` 来更新。
