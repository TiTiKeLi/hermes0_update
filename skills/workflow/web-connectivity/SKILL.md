---
name: web-connectivity
description: 容器内网络连接诊断与Web数据采集 — 从Hermes容器内测试联网、调用API、抓取页面数据的系统化方法论
category: workflow
platforms: [linux]
related_skills: [health-monitor, error-recovery, verification-before-completion]
triggers:
  keywords:
    - 联网检查
    - 网络不通
    - 外网访问
    - 查行情
    - 股票数据
    - 网络诊断
    - 拉取数据
    - API调用
    - URL请求
    - 网页抓取
    - 数据采集
    - 爬虫
    - network test
    - connectivity check
    - fetch data
    - web API
    - stock data
    - scrape
    - 访问不了
    - 连不上
    - 超时
    - 联网
    - 查资料
    - 查一下
    - python报错
    - urllib失败
    - ssl证书
    - 编码问题
    - gbk乱码
    - 中文乱码
---

# Web Connectivity — 容器内联网诊断与数据采集 v1

## 核心问题

Hermes 容器内可以访问外网（curl / Python urllib 均可），但以下常见原因会导致**误报"网络不通"**：

1. **Shell 引号问题**：`python3 -c "..."` 内嵌多层引号/反斜杠会挂死 → 误判为网络超时
2. **SSL 证书路径**：Python 默认 CA 证书路径不在标准位置
3. **编码问题**：部分中文 API 返回 gbk 编码，Python 默认 utf-8 解码失败
4. **缺少工具**：没有 `web_search` / `browser` 工具 → 但可用 curl + Python 替代

---

## 1. 边界条件（BOUNDARIES）

### 入口条件
- 用户反馈"网络不通"或"连不上外网"
- 需要从外部 API 获取数据（行情、新闻、文档）
- 爬取网页内容
- 验证容器网络是否正常

### 跳过条件（一条即跳过）
- [ ] 用户明确说"不需要联网"
- [ ] 任务本身不依赖外网（纯本地操作）
- [ ] 目标 API/站点已知被墙或已下线

### 中止条件（执行中，一条即停）
- [ ] 连续 3 种方法均超时 → 报告网络不可达，不继续尝试
- [ ] API 返回明确错误（403/429 未配置认证）
- [ ] 用户切入其他任务

---

## 2. 决策矩阵（DECISION MATRIX）

| 场景 | 方法 | 工具 | 说明 |
|------|------|------|------|
| 快速验证网络可达 | `curl -sI https://github.com` | terminal | 最快，不受 Python 影响 |
| 诊断具体故障 | 写 `.py` 文件跑 urllib | write_file + terminal | ✅ **推荐** —— 避免 shell 引号问题 |
| 拉取结构化数据（JSON） | Python urllib + json.loads | write_file + terminal | 写文件再跑，不要用 `-c` |
| 爬取网页（HTML） | curl + grep / Python re | terminal | 简单页面用 grep 匹配即可 |
| 中文乱码 | `.decode("gbk")` 或 `encoding="gbk"` | Python 脚本 | 腾讯/新浪 API 常见 |
| SSL 握手失败 | 检查 CA 证书路径 `/usr/lib/ssl/cert.pem` | terminal | curl 自带证书，Python 可能没有 |
| 需要批量并行请求 | execute_code 工具 | execute_code | 适合 >3 个请求 + 处理逻辑 |

---

## 3. 原子步骤（STEPS）

### Step 0: 引号陷阱检查 —— 先自查测试方法
**⚠️ 关键教训：`python3 -c "..."` 在 terminal 工具中遇到复杂引号/反斜杠会 hang。**

**输入**：需要写一个 Python 网络请求脚本
**工具**：terminal
**操作**：
1. 如果当前使用 `python3 -c "..."` 且包含多行、引号嵌套、反斜杠 → **立即停止**
2. 改用 write_file 写入 `.py` 文件
3. 再 `python3 /tmp/<name>.py` 执行
**验证**：`.py` 方式不会超时挂死
**产出**：可靠的 Python 脚本执行

---

### Step 1: 网络连通性诊断
**输入**：用户反馈网络不通
**工具**：terminal
**操作**：
```bash
# 1. 基础 shell 是否正常
pwd

# 2. curl 测试（最可靠 —— curl 自带 CA 证书）
timeout 8 curl -sI -o /dev/null -w "%{http_code} %{time_total}s" https://github.com
timeout 8 curl -sI -o /dev/null -w "%{http_code} %{time_total}s" https://www.baidu.com

# 3. Python urllib 测试（写 .py 文件，不要用 -c）
# 3. Python urllib 测试
# 写 `/tmp/connectivity_test.py` 脚本方式执行（不要用 `-c` 参数）
# 示例见 Step 3 的脚本模板

**验证**：以上至少有一个站点返回 HTTP 2xx → 网络正常
**产出**：网络是否可达的确诊结论

---

### Step 2: SSL/CA 检查（urllib 失败时）
**输入**：curl 可通但 Python urllib 超时/报错
**工具**：write_file + terminal
**操作**：
```python
# /tmp/ssl_check.py
import ssl, os
print("SSL version:", ssl.OPENSSL_VERSION)
print("CA path:", ssl.get_default_verify_paths())
print("CA exists:", os.path.exists("/usr/lib/ssl/cert.pem"))
```
**验证**：CA 文件存在且大小 > 0
**产出**：确认 SSL 配置正常

---

### Step 3: 拉取 JSON API 数据
**输入**：需要调用外部 API 获取结构化数据
**工具**：write_file + terminal
**操作**：
```python
# /tmp/fetch_data.py
import urllib.request, json
headers = {"User-Agent": "Mozilla/5.0"}
url = "..."  # 目标 API
req = urllib.request.Request(url, headers=headers)
r = urllib.request.urlopen(req, timeout=8)
data = json.loads(r.read())
# 处理数据...
```
**验证**：read_file 回读输出，确认数据格式正确
**产出**：解析后的结构化数据

---

### Step 4: 中文编码处理
**输入**：API 返回内容含乱码或解码错误
**工具**：write_file + terminal
**操作**：
```python
# 优先尝试 gbk（腾讯财经常用）
text = raw.decode("gbk", errors="replace")
# 回退 utf-8
text = raw.decode("utf-8", errors="replace")
```
**验证**：输出能看到中文（如"上证指数"）
**产出**：正确解码的中文数据

---

### Step 5: 清理临时文件
**输入**：数据采集完成
**工具**：terminal
**操作**：`rm -f /tmp/*.py /tmp/fetch_*.py`
**验证**：不阻塞——非关键步骤，跳过不影响
**产出**：临时文件已清理

---

## 4. 工具/Skill 联动表（TOOL CHAIN MAP）

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill |
|------|-----------|-----------|-----------|-------------|
| Step 0 | terminal | 无 | 无 | 无 |
| Step 1 | terminal | 无 | 无 | health-monitor（网络诊断语境） |
| Step 2 | write_file, terminal | 无 | /tmp/ssl_check.py | 无 |
| Step 3 | write_file, terminal | 无 | /tmp/fetch_data.py | verification-before-completion |
| Step 4 | write_file, terminal | 无 | /tmp/fetch_data.py | 无 |
| Step 5 | terminal | 无 | 无 | 无 |

---

## 5. 反馈回路（FEEDBACK LOOP）

### 写后验证
- write_file 后 → terminal 执行 → 捕获 stdout/stderr → 检查 exit_code
- JSON 数据：json.loads 验证
- 编码：确认输出不含 `\uXXXX` 转义

### 已知可用的 API 端点
详情见 `references/known-apis.md`：
- 腾讯财经 `qt.gtimg.cn` —— A股/港股/美股实时行情
- 新浪财经 `hq.sinajs.cn` —— 美股实时行情
- Yahoo Finance `query1.finance.yahoo.com` —— 美股指周K线数据
- Google Finance `www.google.com/finance/quote/` —— 需 HTML 解析

### 已知陷阱
- `python3 -c "..."` 带多层引号 → 改 .py 文件（❗第一优先级）
- 腾讯 `usINX` 编码 = `usINX`（非 `usSPX`）
- 新浪 API 返回 `var hq_str_xxx="..."` 格式，需 split 后再解析
- Yahoo Finance 对 `^IXIC` 有时 SSL 握手超时（重试或换源）
- Google Finance HTML 结构不稳定，数据可嵌在任意的 JSON 块中
- 中文 API 常用 gbk/gb2312 编码（腾讯、新浪），Yahoo/Google 用 utf-8
