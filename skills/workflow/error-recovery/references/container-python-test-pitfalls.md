# 容器内 Python 测试陷阱

## 问题：`python3 -c` 多行代码挂死

### 症状
- `python3 -c "代码..."` 在主终端正常，但在 `terminal()` 工具中超时
- 复杂嵌套引号（单引号内套双引号、`\n` 换行、`&` 拼接）导致 shell 解析异常
- 管道链 `cmd1 && cmd2 && py -c "..."` 卡死在 Python 解释器启动阶段

### 根因
Hermes 的 `terminal()` 工具将整个命令传给 `/usr/bin/bash -c`。当 `python3 -c` 参数中有 shell 元字符（引号、`$`、反斜杠、换行）时，bash 会先解析它们，导致传给 Python 的代码被截断/变形，Python 因此阻塞等待更多输入。

### 修复

| 做法 | 命令 | 可靠性 |
|------|------|--------|
| ❌ 禁止 | `python3 -c "import ssl, urllib...\ntry:\n  r = urlopen(...)"` | 嵌套引号 + 显式换行 = 挂死 |
| ❌ 慎用 | `python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"` | 只有一行且无嵌套引号时 OK |
| ✅ 推荐 | 写入 `.py` 文件 → `python3 /tmp/test.py` | 零引号问题，可调试 |
| ✅ 推荐（单行） | 管道：`echo "print('hi')" | python3` | 回避引号解析 |

### 验证命令

```bash
# ✅ 可用的测试方式
timeout 8 python3 /tmp/test_net.py
timeout 8 curl -sI https://github.com
timeout 8 echo 'import urllib.request; print(urllib.request.urlopen("https://github.com", timeout=5).status)' | python3

# ❌ 会挂死的方式
python3 -c "..."   # 含嵌套引号或多行时
python3 -c '...'   # 同上
```

## 容器网络诊断备忘

### 步骤
1. 基础确认：`curl -sI https://github.com`（最快，不受 Python 影响）
2. 独立交叉验证：curl + Python(.py) + 必要时 wget
3. Python 专用：写脚本到 `/tmp/` 再执行
4. 如果 curl 通但 Python 不通 → 多半是 Python 环境问题（SSL 证书/引号解析），不是网络
5. 如果用户说"X 能用" → 相信用户，主动找自己测试方式和用户操作方式的差异

### 常见的"假网络不通"根因
- `python3 -c` 引号挂死（最常见！）
- SSL 证书过期 → 加 `ctx = ssl.create_default_context(); ctx.verify_mode = ssl.CERT_NONE` 检查
- 特定域名 TLS 协议不匹配 → curl 用 `--tlsv1.2` 或 `-k`
- 代理环境变量未设置 → `env | grep -i proxy`
