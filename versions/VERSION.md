# Hermes GUI 版本管理

## 版本列表

| 版本 | 日期 | 变更 | 文件 |
|------|------|------|------|
| v1.0 | 2026-07-24 | 初始版本：基础三栏布局 | gui.html, gui.py |
| v1.1 | 2026-07-25 | 添加 Skills 触发关键词显示 | gui.html |
| v1.2 | 2026-07-25 | 修复 IPv6 问题 (localhost→127.0.0.1) | start-dashboard.bat |
| v2.0 | 2026-07-25 | 重构为官方三栏布局，添加命令面板 | gui.html |
| v2.1 | 2026-07-25 | 修复会话读取 (JSONL→state.db) | gui.py |
| v2.2 | 2026-07-25 | 修复聊天输入框固定底部 | gui.html |
| v2.3 | 2026-07-25 | 添加语义搜索 (Ollama nomic-embed-text) | gui.py, gui.html |

## 回滚方法

```bash
# 回滚到指定版本
docker cp versions/v2.0/gui.html hermes:/opt/data/gui.html
docker cp versions/v2.0/gui.py hermes:/opt/data/gui.py

# 重启 GUI
docker exec hermes pkill -f "python3 /opt/data/gui.py"
docker exec -d hermes python3 /opt/data/gui.py
```

## 备份命令

```bash
# 备份当前版本
Copy-Item "C:\Users\Lsc\.hermes\gui.html" "C:\Users\Lsc\.hermes\versions\v2.3\gui.html"
Copy-Item "C:\Users\Lsc\.hermes\gui.py" "C:\Users\Lsc\.hermes\versions\v2.3\gui.py"
```
