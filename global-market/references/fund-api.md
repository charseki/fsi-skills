# 天天基金净值 API (fundgz.1234567.com.cn)

## 接口

```
GET https://fundgz.1234567.com.cn/js/{code}.js
```

## 响应格式

JSONP 回调包裹：

```json
jsonpgz({
  "fundcode": "016814",
  "name": "国联中证煤炭指数C",
  "jzrq": "2026-05-15",
  "dwjz": "2.0550",
  "gsz": "2.0947",
  "gszzl": "1.93",
  "gztime": "2026-05-18 15:00"
})
```

## 字段说明

| 字段 | 含义 | 说明 |
|------|------|------|
| fundcode | 基金代码 | 6位数字 |
| name | 基金全名 | 含份额类型（A/C） |
| jzrq | 净值日期 | 最近公布的官方净值日期 |
| dwjz | 单位净值 | 官方公布的净值，非估算 |
| gsz | 估算净值 | 盘中实时估算，非官方值 |
| gszzl | 估算涨跌幅 | 百分比，如 1.93 表示 +1.93% |
| gztime | 估算时间 | 估算净值对应的时刻 |

## 使用方法

```bash
curl -s "https://fundgz.1234567.com.cn/js/016814.js"
```

配合 Python 解析：

```python
import re, json

# 注意：API 返回 jsonpgz({...});  末尾有 ); 不是单纯的 )
# 必须用非贪婪匹配 + 可选分号
resp = raw_response  # 原始 JSONP 字符串
match = re.search(r'jsonpgz\((.+?)\)\s*;?\s*$', resp)
if not match:
    raise ValueError("无法解析基金 API 响应")
data = json.loads(match.group(1))
```

**⚠️ 常见陷阱**：`re.search(r'jsonpgz\((.*)\)', resp)` 的写法有问题：
- `(.*)` 是贪婪匹配，如果 JSON 内容包含 `)` 会匹配到错误位置
- 末尾 `;` 不被处理，payload 是 `jsonpgz({...});` 而非 `jsonpgz({...})`
- 正确写法：`r'jsonpgz\((.+?)\)\s*;?\s*$'`

## 注意事项

- `gsz` / `gszzl` 是**盘中估算值**，非官方净值，误差通常在 ±0.5% 以内
- 官方净值（`dwjz`）一般在每个交易日 19:00-22:00 更新
- 非交易日调用返回的是最近一个交易日的估算数据
- C 类份额和 A 类份额代码不同，需分别查询
