# CONTEXT — Hermes Project Context Document

> 单一事实来源。所有跨文件变量、配置覆盖链、模块依赖关系都记录于此。

## 配置拓扑总览

```
Windows 宿主机层
├── ~\.wslconfig — WSL2 网络/资源参数
├── ~\.docker\daemon.json — Docker 引擎级 DNS 配置
├── ~\AppData\Roaming\Docker\settings-store.json — Docker Desktop GUI 代理

├── C:\Users\Lsc\.hermes\ (bind mount → /opt/data)
│   ├── docker-compose.yml  — 容器编排
│   ├── Dockerfile           — 镜像构建
│   ├── .env                 — 环境变量
│   ├── config.yaml          — Hermes 配置
│   ├── network-repair.ps1   — 网络修复脚本
│   ├── CONTEXT.md           ← 本文件
│   └── healthcheck.sh       — 健康检查

├── skills/
│   └── architecture/config-unification/  — 配置统筹方法论
```

## 变量注册表

| 变量 | 源 | 最终值 | 备注 |
|------|------|-------|------|
| HTTP_PROXY | 基础镜像 ENV | unset | entrypoint 清除 |
| HTTPS_PROXY | 基础镜像 ENV | unset | entrypoint 清除 |
| NO_PROXY | 基础镜像 ENV | unset | entrypoint 清除 |
| DEEPSEEK_API_KEY | .env | 有效 | 用于 DeepSeek API |
| HERMES_AUTH_TOKEN | .env | hermes-dev | Gateway 鉴权 |
| TZ | docker-compose | Asia/Shanghai | |

## 覆盖链

```
Layer 0: 基础镜像 Dockerfile ENV
Layer 1: docker-compose environment:
Layer 2: .env (env_file)
Layer 3: entrypoint sh -c "unset ..." ← 修复点
Layer 4: exec → /proc/1/environ (最终值)
```

## 配置关键端口

| 端口 | 用途 | 状态 |
|------|------|------|
| 8642 | Hermes Gateway | 暴露 |
| 8644 | Hermes 备用 | 暴露 |
| 18931 | host_proxy.py | 停止（已废弃） |
| 3128 | Docker Desktop 内置代理 | 配置但未运行 |

## 已知陷阱

### P1: 基础镜像 ENV 不可删除
HTTP_PROXY="" 和 NO_PROXY=* 硬编码在基础镜像中，只能通过 entrypoint unset 清除。

### P2: docker exec ≠ 进程环境
docker exec 显示 Docker 默认环境，非 PID 1 实际环境。查实值用 /proc/1/environ。

### P3: NO_PROXY=* 阻塞所有代理
与 Docker Desktop 引擎代理冲突，导致请求挂死。已在 entrypoint 中 unset。

### P4: 大写 vs 小写代理变量
HTTP_PROXY 和 http_proxy 必须同步设置，不同工具认不同版本。

### P5: web.search_backend 为空
search_backend='' 导致"联网"操作失败。已修复为 duckduckgo。

### P6: terminal.docker_env 死代理
指向不运行的 host_proxy.py:18931。已清除为 {}。

## 故障症状注册表

### S1: OpenAI/GitHub 超时，百度/DeepSeek 正常
→ 代理变量冲突。命令: unset NO_PROXY; curl https://api.openai.com

### S6: "联网百度"无网络，但 GitHub 可访问
→ web.search_backend 为空 或 terminal 死代理。
修复: config.yaml 中 search_backend=duckduckgo, docker_env={}

## 修改历史

| 日期 | 修改 | 影响文件 |
|------|------|---------|
| 2026-07-25 | 修复基础镜像代理变量 | docker-compose.yml, entrypoint |
| 2026-07-25 | DNS 兜底 8.8.8.8 + 223.5.5.5 | docker-compose.yml, daemon.json |
| 2026-07-25 | 创建 CONTEXT.md + config-unification 技能 | 新文件 |
| 2026-07-25 | 清除 terminal.docker_env 死代理 | config.yaml |
| 2026-07-25 | 配置 web 搜索后端 duckduckgo | config.yaml |

## 文件结构说明

### 根目录（62 个文件）
所有 Hermes 启动时必须找到的配置文件和核心脚本。
**不要移动这些文件**，Hermes 通过硬编码路径引用它们。

| 类别 | 文件 | 能否移动 |
|------|------|---------|
| 配置 | config.yaml, docker-compose.yml, Dockerfile, .env | ❌ Hermes 直接引用 |
| 核心脚本 | gui.py, dashboard.py, healthcheck.sh, host_proxy.py 等 | ❌ volume 根是工作目录 |
| 身份 | MEMORY.md, SOUL.md, USER.md | ❌ Hermes 启动时读取 |
| 技能 | skills/ | ❌ Hermes 技能系统引用 |
| 启动脚本 | start-*.ps1, *.vbs, *.bat | ⚠️ 可移，但已 gitignored |

### 数据目录（全部被 .gitignore 排除）
| 目录 | 内容 | 安全级别 |
|------|------|---------|
| sessions/ | 对话历史 | 🔴 包含用户输入和 AI 回复 |
| memories/ | 长期记忆 | 🔴 包含系统知识 |
| incoming/ | 请求转储、JSONL 日志 | 🔴 包含 API 请求内容 |
| cache/ | 缓存文件 | 🟡 无敏感信息但无版本价值 |
| logs/ | 运行时日志 | 🟡 可能含错误堆栈 |
| backups/ | 配置备份 | 🟡 含配置文件历史版本 |
| cron/output/ | 定时任务输出 | 🟡 运行时日志 |

### .gitignore 排除模式覆盖率（22 类）
`
数据库     *.db, *.db-wal, *.shm, *.sqlite
缓存       __pycache__/, cache/, *.pyc, *.json 大文件
日志       *.log, logs/
数据目录   sessions/, memories/, incoming/
备份       backups/, *.bak
密钥       .env, auth.json, wechat_qr.*
运行时状态  gateway_state.json, ticker_*, heartbeat_last.json
定时输出   cron/output/
临时文件   *.lock, *.pid
大型文件   *.zip, tirith, crewAI.zip
会话       session_*.json, sessions/*.json
请求转储   request_dump_*
JSONL      *.jsonl
音频       *.mp3
Python 编译 *.pyc, *.pyo, *.pyd
运行时JSON  registry.json, trusted.json, model_catalog.json
配置备份   config.yaml.bak, docker-compose.yml.bak
启动脚本   *.vbs, *.bat
OS 文件    Thumbs.db, .DS_Store
版本历史   versions/
测试文件   test_embed.py, _test_ds.py
空目录     bin/
技能缓存   skills/.curator_*
