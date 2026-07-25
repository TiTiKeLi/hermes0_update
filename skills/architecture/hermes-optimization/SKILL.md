---
name: hermes-optimization
description: >-
  Hermes Docker 容器的全量优化。涵盖 MEMORY.md 压缩、图片错误修复、
  回复格式固化、连接错误修复(host_proxy.py)、网络诊断五个维度。
category: architecture
platforms: [linux, wsl]
related_skills: [github-discover, memory-compactor, agent-memory-architecture]
triggers:
  keywords:
      - 优化
      - optimize
      - 性能
      - docker容器
      - 错误修复
      - 回复格式
---

# Hermes 容器优化 (Hermes Optimization)

## 概述
Hermes Docker 容器的全量优化。涵盖 MEMORY.md 压缩、图片错误修复、回复格式固化、连接错误修复、网络诊断五个维度。所有 "Hermes" 指代 `C:\Users\Lsc\.hermes` 挂载到 `/opt/data` 的 Docker 容器 (`hermes-agent:with-deps`)。

---

## 1. MEMORY.md 压缩

> ⚠️ **已过时** — 自动化的记忆压缩已迁移至独立 skill `memory-compactor`（`memory_compactor_v2.py`，每5分钟 cron 自动运行）。本节保留仅作早期手动压缩的历史参考。
> 
> 当前压缩架构 → `skill memory-compactor`
> 记忆架构设计模式（含 MemGPT/Mem0 对比）→ `skill agent-memory-architecture`

### 前置条件
- 文件位于 `C:\Users\Lsc\.hermes\MEMORY.md`
- 原始 57 行，冗余 prose + 扁平 fact 混合

### 步骤
| # | 操作 | 说明 |
|---|------|------|
| 1 | 分离 IDENTITY 区 | host/ollama/model/interface/lang 合并为 5 行 key:value |
| 2 | 压缩 FACTS 区 | id:N[tag] 格式，`·` 分隔多属性，`→` 表示映射 |
| 3 | 去重 | 删除 IDENTITY 与 FACTS 重叠条目 |
| 4 | 去空行 | 所有无信息行全部删除 |

### 结果
- 57 行 → 28 行（-51%）
- FACTS 保留所有 id 与 tag 不变，仅压缩值表达式

---

## 2. 图片错误修复

### 错误现象
```
ERROR: Cannot read "C:\...xxx.jpg" (this model does not support image input).
```
- **频率**:每次 WeChat 收到图片都触发
- **根因**: `image_input_mode: auto` 尝试读取图片→底层模型不支持 vision

### 修复
| 配置项 | 原值 | 新值 |
|--------|------|------|
| `agent.image_input_mode` | `auto` | `skip` |

### 原理
`skip` 模式直接跳过图片消息而不尝试读取，消除 error log 和用户通知。

---

## 3. Caveman Reply Skill

### 文件
`skills/behavior/caveman-reply/SKILL.md`

### 输出规则
| 规则 | 内容 |
|------|------|
| 区块 | 仅 2 段：阶段性成果 · 结论 |
| 格式 | `>` 标记阶段，`**` 标记结论 |
| 长度 | 单条 ≤ 80 字符 |
| 禁项 | 无 prose、无解释、无过渡句 |

### 触发
会话加载时自动激活，全局生效（含错误/确认/结果）。

---

## 优化倾向

### 信息密度优先
- prose → key:value 原子事实
- 时间戳消歧（SimpleMem 式语义压缩）
- 标签分类（Mem0 式提取+分桶）

### 噪音消除优先
- 重复错误 → skip 静默处理
- 冗长回复 → caveman 2 段格式
- 过渡句 → 直接输出结果

### 可维护性优先
- 所有文件在 `C:\Users\Lsc\.hermes\` 下
- 每项修改附带回滚预案
- Skill 文档即变更日志

---

## 4. 连接错误修复

### 错误现象
```
WARNING: API call failed (attempt 1/3) Connection error.
```
重复 3 次重试后：`ERROR: API call failed after 3 retries. Connection error.`

### 根因
`docker-compose.yml` 硬编码了失效的代理地址：
```yaml
- HTTP_PROXY=http://host.docker.internal:18931
- HTTPS_PROXY=http://host.docker.internal:18931
```
宿主机无代理运行在 18931 端口，导致容器所有外部 API 调用均无法建立连接。

### 修复
| 配置项 | 原值 | 新值 |
|--------|------|------|
| `docker-compose.yml` environment | `HTTP_PROXY=http://host.docker.internal:18931` | 整行删除 |
| `docker-compose.yml` environment | `HTTPS_PROXY=http://host.docker.internal:18931` | 整行删除 |
| 容器生命周期 | — | `docker compose down && docker compose up -d` |

### 验证
- `docker exec hermes env` → PROXY 变量正确指向 host_proxy.py
- 容器通过 host.docker.internal:18931 经 host_proxy.py 中转访问 DeepSeek API

### 重要发现
- `host_proxy.py` (`C:\\Users\\Lsc\\.hermes\\host_proxy.py`) 是运行在宿主机的 Python 正向代理

### ⚡ 新陷阱：NO_PROXY 排除外网站点（2026-07-24）
即使 host_proxy.py 正常运行，GitHub/PyPI 等下载仍可能失败。
**根因**：`NO_PROXY` 包含了 `github.com,api.github.com,pypi.org,gitlab.com,bitbucket.org`，这些站点绕过代理直连 → Docker bridge NAT 不转发 → TCP 超时。
**修复**：从 NO_PROXY 中移除这些站点，或临时 `unset HTTPS_PROXY http_proxy https_proxy HTTP_PROXY; export NO_PROXY="*"` 走直连。
**参见**：`references/network-diagnosis.md` → 模式 E

### ⚡ Git 克隆实战（2026-07-25）
当需要从 GitHub 克隆项目到 Hermes 时（如 external-adaptor 管道的 Step 0）：

```bash
# 代理不通时，走直连
unset HTTPS_PROXY http_proxy https_proxy HTTP_PROXY
export NO_PROXY="*"
GIT_TERMINAL_PROMPT=0  # 禁用 git 凭据弹窗

# 连通性测试
git ls-remote --heads https://github.com/owner/repo.git 2>&1 | head -3

# 小型仓库直接克隆
git clone --depth 1 https://github.com/owner/repo.git /opt/data/incoming/repo

# 大型仓库（>3000 files）需要更长超时
# 会因 60s terminal 超时而签出失败，需要额外 restore：
# git clone --depth 1 URL /path  # 可能显示"checkout failed"
# cd /path && git restore --source=HEAD :/
```

**已知问题**：
- `NO_PROXY='*'` 使 curl 完全不经过代理 → 仅对可达站点有效
- 大型仓库（>4000 files）60s 内无法完全签出 → 优先选轻量项目
- `git clone` 需要交互式认证的项目会报 "could not read Username" → 选公开仓库
- 搜索 API（`api.github.com/search/...`）响应慢（>10s），而单仓库查询快（<5s）→ 优先用已知 URL 而非搜索
- 监听 `127.0.0.1:18931`，支持 HTTP CONNECT 隧道和直接 HTTP 转发
- 使用 `select` 多路复用实现双向 TCP 转发，无线程竞争
- **不经过 Hiddify VPN**：host_proxy.py 直接创建原生 socket 连接，因此只能到达境内可达站点（DeepSeek/百度/GitHub/PyPI/微信）
- 境外被墙站点（Google/Bing/docker.io）不可达，需要 Hiddify 配合
- Hiddify (sing-box 内核) 监听端口 12334/12337，但 HTTP 代理接口未开放给容器使用

### 当前架构
```
容器(hermes) → HTTP_PROXY → host.docker.internal:18931 → host_proxy.py → 原生socket → 目标站点
                                                                           ↛ Hiddify VPN(未集成)
```

---

## 5. 网络诊断

### 参考文档
`references/network-diagnosis.md` — 容器网络故障排查流程

涵盖：
- DNS/路由/端口/TCP 分层排查流程
- 常见故障模式（代理不通/全超时/DNS 失败/大小写不匹配）
- 快速诊断脚本
- 已知陷阱

### 核心原则
1. 不要用 ping/curl/wget — 精简容器中不存在，误判为"网络不通"
2. 不要用 bash `/dev/tcp` — 受限网络会挂死，导致 terminal 超时阻断
3. `host.docker.internal` 是 Docker 内部网关（192.168.65.254），不是宿主机真实 IP
4. Python 只认小写 `http_proxy`，大写版本被忽略
5. `connect_ex` 返回码：0=OK, 111=拒绝, 110=超时

### 终端容器网络架构约束（重要）

Hermes 使用 `terminal.docker_image: nikolaik/python-nodejs:python3.11-nodejs20` 作为独立的工具容器执行 `terminal()` 命令。该容器与 Hermes 主容器通过共享 volume `/opt/data` 交换文件。

**网络隔离机制**：
- 工具容器默认使用 Docker bridge 网络，完全独立于 Hermes 主容器的网络栈
- 即使主容器网络通，工具容器仍可能无外网路由
- 工具容器不持久化（每次重启恢复镜像原始状态），apt install / pip install 重启后丢失

**故障现象**：
- 工具容器内 TCP 连接 `8.8.8.8:53` 超时（`connect_ex=110`）
- `host.docker.internal` 不可达
- Hermes 主容器本身网络正常（能访问 Ollama 等）

**修复路径**：
| 方案 | 操作 | 效果 | 持久化 |
|------|------|------|--------|
| `--network=host` | `config.yaml` 设 `terminal.docker_extra_args: ["--network=host"]` + 重启 | 容器复用宿主机网络栈 | ✅ 配置持久，需重启 |
| 宿主机 HTTP 代理 | 在 Windows 开代理端口，容器通过 `host.docker.internal:PORT` 访问 | 仅代理端口可通 | ❌ 依赖代理运行 |
| 手动下载 | Windows `git clone` / 浏览器下载到共享目录 `/opt/data/` | 绕开容器网络限制 | ✅ 文件立即可用 |

**注意**：WSL2 + Docker Desktop 的 `--network=host` 是模拟实现，底层仍走 Windows NAT，不一定对所有场景有效。如果 `--network=host` 后仍不通，优先选手动下载方案。

---

## 5. 网络拓扑总结

### 容器网络路径（含 VibeThinker 子 Agent）
```\n容器(hermes) ←→ host.docker.internal (IPv6 ULA: fdc4:f303:9324::254)
    ↓ HTTP_PROXY=http://host.docker.internal:18931
    ↓
host_proxy.py (PID 29952, 127.0.0.1:18931)
    ↓ 原生 TCP socket
    ↓
目标站点:
  ✅ DeepSeek API (api.deepseek.com)        → 必需·正常
  ✅ WeChat iLink (ilinkai.weixin.qq.com)   → 必需·正常
  ✅ Ollama (host.docker.internal:11434)     → 本地推理·正常（仅主容器可达）
  ✅ 百度/GitHub/PyPI                        → 可选·正常
  ❌ Google/Bing/docker.io                   → GFW封锁·除非集成Hiddify

━━━ VibeThinker-3B 子 Agent 架构 ━━━
Ollama: host.docker.internal:11434
模型: VibeThinker-3B:latest
可达范围:
  ✅ execute_code（主容器）→ urllib 直连 Ollama
  ❌ terminal（工具容器）→ 无网络路由，不可达

工作分配:
  主 Agent (Hermes, full model):  复杂推理·架构设计·SKILL生成·搜索编排
  VibeThinker-3B (sub-agent):     高频固定任务（记忆压缩/日志分类/心跳摘要）

已部署 cron:
  - memory-compactor: 每5min no_agent script=memory_compactor_vibe.py
  - heartbeat-vibe:   每30min no_agent script=heartbeat_vibe.py
```
```

### 宿主机代理进程
| 进程 | PID | 端口 | 类型 |
|------|-----|------|------|
| `host_proxy.py` | 29952 | 18931 | HTTP正向代理 (TCP forward) |
| `Hiddify.exe` | 20872 | 12334/12337 | sing-box VPN客户端 (未与容器集成) |
| `com.docker.backend` | 17544 | 8080/8118/8888 | Docker Desktop内部服务 |

### 如需访问被墙站点（Google等）
1. 确认 Hiddify 开启 HTTP 代理监听
2. 将 `HTTP_PROXY` 改为指向 Hiddify 的 HTTP 代理端口
3. 重启容器

---

## 6. 工具容器配置

### 问题
工具容器（terminal/代码执行容器）无网络代理配置、无持久化存储。

### 修改
| 配置项 | 原值 | 新值 | 说明 |
|--------|------|------|------|
| `terminal.backend` | `local` | `docker` | 启用 Docker 容器执行 |
| `terminal.docker_env` | `{}` | 含 HTTP_PROXY/HTTPS_PROXY/NO_PROXY | 通过 host.docker.internal:18931 代理联网 |
| `terminal.docker_volumes` | `[]` | 2 个挂载卷 | 持久化数据 + 项目代码 |
| `terminal.docker_mount_cwd_to_workspace` | `false` | `true` | 挂载当前目录到容器工作区 |
| `terminal.working_dir` | `.` | `/workspace/project` | 容器内工作目录 |
| `terminal.container_cpu` | `1` | `2` | 双核 |
| `terminal.container_memory` | `5120` | `8192` | 8GB 内存 |
| `terminal.container_disk` | `51200` | `102400` | 100GB 磁盘 |
| `terminal.timeout` | `180` | `300` | 5 分钟超时 |
| `terminal.docker_extra_args` | `["--network=host"]` | `[]` | 移除 host 网络，用 bridge+host.docker.internal |

### 挂载卷
| 宿主机路径 | 容器路径 | 用途 |
|-----------|---------|------|
| `C:\Users\Lsc\.hermes\toolbox` | `/workspace/data` | 工具容器持久化数据 |
| `C:\DDisk\TestGroup\ClaudeCode-PAI\AudioVectorSystem` | `/workspace/project` | 项目代码 |

### 网络路径
```
工具容器 → HTTP_PROXY → host.docker.internal:18931 → host_proxy.py → 原生socket
                                        ↕ 共享挂载卷
主容器(hermes) ← 同一代理链路
```

---

## 变更清单

| 文件 | 操作 | 回滚 |
|------|------|------|
| `MEMORY.md` | 57→28 行 | 回退到之前内容 |
| `config.yaml` L10 | `auto` → `skip` | 改回 `auto` |
| `config.yaml` terminal节 | 全面修改网络/资源/持久化 | 还原默认值 |
| `docker-compose.yml` | 代理配置:删除→恢复 | 切换代理源 |
| `C:\Users\Lsc\.hermes\toolbox` | 新建目录 | 删除目录 |
| `skills/behavior/caveman-reply/SKILL.md` | 新建 | 删除文件 |
| `skills/architecture/hermes-optimization/SKILL.md` | edit | 回退到旧版本 |
