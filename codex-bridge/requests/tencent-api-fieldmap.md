# 腾讯API (qt.gtimg.cn) 字段映射表
## 用于 Codex 修复 BUG-2 (行业) 和 BUG-3 (市值)
## 2026-07-26

## 已知字段 (以 贵州茅台 sh600519 为例)
- parts[1]  = 名称          (贵州茅台)
- parts[2]  = 代码          (600519)
- parts[3]  = 当前价         (1297.41)
- parts[4]  = 昨收           (1292.01)
- parts[5]  = 今开           (1305.00)
- parts[6]  = 成交量(手)     
- parts[7]  = 成交额         
- parts[31] = 最高价         
- parts[32] = 最低价         
- parts[39] = 动态市盈率      (19.61)  ← 正确的
- parts[44] = 流通市值(？)    
- parts[45] = 总市值(？)      
- parts[46] = 市净率         
- parts[53] = ROE(%)         
- parts[54] = 净利率(%)      
- parts[55] = EPS(每股收益)  
- parts[57] = ❌ 当前误判为"行业"，实际是行业指数代码 (462224.2878)

## 行业字段问题
腾讯API的行业名可能在 parts[58] 或 parts[60] 附近
需要脚本验证：遍历 parts[55:70] 找出文本型字段

## 市值字段问题
腾讯API field 45 的单位可能不是"万"，而是"元"
茅台 12.56亿股 × 1297.41元/股 ≈ 1.63万亿
如果 parts[45] = "162923889600" → ÷100000000 = 1.63万亿 (单位是元)
如果 parts[45] = "16292389" → ÷10000 = 1629.24亿 (单位是万) — 也不对
需要实测验证。

## 验证方法
```python
import urllib.request
url = 'https://qt.gtimg.cn/q=sh600519'
req = urllib.request.Request(url, headers={'Referer':'https://finance.qq.com','User-Agent':'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=8)
raw = resp.read().decode('gbk')
parts = raw.strip().split('=',1)[1].strip(';').strip('"').split('~')
for i in range(40, 70):
    print(f'parts[{i}] = {parts[i]!r}')
```
