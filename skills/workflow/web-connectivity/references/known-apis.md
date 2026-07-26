# 已知可用的数据源 API

## 腾讯财经 (qt.gtimg.cn)
**格式**：`v_<code>="1~名称~代码~最新~昨收~今开~成交量~...~涨跌额~涨跌幅~..."`
**编码**：gbk
**请求示例**：
```
https://qt.gtimg.cn/q=sh000001,sh000300,hkHSI,usINX,usDJI,usIXIC
```
| 代码 | 含义 |
|------|------|
| `sh000001` | 上证综指 |
| `sh000300` | 沪深300 |
| `hkHSI` | 恒生指数 |
| `usINX` | S&P 500 |
| `usDJI` | 道琼斯 |
| `usIXIC` | 纳斯达克 |
| `hkHSCE` | 国企指数 (H股) |
| `sh000688` | 科创50 |

## 新浪财经 (hq.sinajs.cn)
**格式**：`var hq_str_<code>="名称,最新价,涨跌幅%,更新时间,涨跌额,开盘,最高,最低,52周高,52周低,成交量,成交额,...";`
**编码**：gbk
**请求示例**：
```
https://hq.sinajs.cn/list=gb_$dji,gb_ixic,gb_$inx
```
| 代码 | 含义 |
|------|------|
| `gb_$dji` | 道琼斯 |
| `gb_ixic` | 纳斯达克 |
| `gb_$inx` | S&P 500 |

## Yahoo Finance (query1.finance.yahoo.com)
**格式**：JSON，带 chart/meta/indicators 结构
**编码**：utf-8
**请求示例**：
```
https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d
```
| 代码 | 含义 | URL编码 |
|------|------|---------|
| `^GSPC` | S&P 500 | `%5EGSPC` |
| `^DJI` | 道琼斯 | `%5EDJI` |
| `^IXIC` | 纳斯达克 | `%5EIXIC` |

**数据路径**：
- `data.chart.result[0].meta.regularMarketPrice` → 当前价
- `data.chart.result[0].meta.chartPreviousClose` → 前收
- `data.chart.result[0].timestamp` → 时间戳数组
- `data.chart.result[0].indicators.quote[0].close` → 收盘价数组
- `data.chart.result[0].indicators.quote[0].open` → 开盘价数组

## 腾讯周K线 (web.ifzq.gtimg.cn)
**格式**：JSON
**编码**：utf-8
**请求示例**：
```
https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,week,,,1,qfq
```
**注意**：仅对 A股/港股 有效，美股（usINX/usDJI等）不支持周K线。

## 谷歌财经 (www.google.com/finance)
**格式**：HTML，数据嵌入在 `<script>` JSON 块中
**请求示例**：
```
https://www.google.com/finance/quote/.INX:INDEXSP
```
**注意**：
- 需要 `User-Agent` 头
- Python urllib 和 curl 可能返回不同 HTML 结构（gzip 差异）
- 数据位置不固定，建议正则搜索 `[price, change_val, change_pct, ...]` 模式
- 不如直接使用腾讯/新浪 API 稳定
