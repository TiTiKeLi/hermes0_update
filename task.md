# Hermes 容器能力审计与激活计划

> **核心思路**：Hermes 已经内置了绝大部分所需能力（会话存储、记忆系统、任务编排、技能系统、MCP、插件等）。本项目不是"开发缺失功能"，而是"审计、配置、激活、集成、加固"。

---

## 第一阶段：现状审计（1-2 天）

### A1：已有能力验证

| 能力 | Hermes 内置状态 | 实际生效？ | 测试方法 |
|------|----------------|-----------|---------|
| 会话存储 | `hermes sessions` SQLite 存储 | ✅ 23 个会话已保存 | `sessions stats` |
| 会话搜索 | `session_search` tool 已启用 | ⚠️ 辅助模型未配置 | 发"帮我找上周的会话" |
| 长期记忆 | `memory: provider: holographic` + hermes-memory-store plugin | ⚠️ `memory_store.db` 状态待确认 | 发"记住我喜欢简洁回答"后重启再问 |
| 内置记忆 | MEMORY.md / USER.md 永久生效 | ❌ 文件不存在 | `ls /opt/data/MEMORY.md` |
| 任务规划 | `todo` tool 已启用 | ⚠️ 未验证 | 发"帮我规划一个 3 步任务" |
| 子 agent | `delegation` tool 已启用 | ⚠️ 未验证 | 发"并发查询三个网站" |
| 技能系统 | `skills` tool + curator | ✅ curator 运行中 | `skills list` |
| 插件系统 | `plugins install` | ✅ 框架就绪 | `plugins list` |
| MCP 服务器 | `mcp add` | ❌ 未配置任何 server | `mcp list` |
| cron 任务 | `cron` + cronjob tool | ✅ 已有定时任务 | `cron list` |
| 跨平台消息 | `messaging` tool | ⚠️ 仅 WeChat 接入 | 触发 messenger 工具 |
| 决策日志 | 需确认 | ❓ | `ls /opt/data/decisions/` |
| 看板 | `kanban` 已启用 | ⚠️ 无实质内容 | `kanban` 命令 |
| 上下文压缩 | `compression` 已启用 | ✅ 自动工作 | 无需测试 |
| Webhook | `hooks` 已启用 | ⚠️ 未配置 | `hooks list` |

### A2：配置盲区清单

| 配置项 | 当前值 | 需要操作 |
|--------|-------|---------|
| `memory.provider` | `holographic` | ✅ 已配（本地运行，无需 API key） |
| `plugins.hermes-memory-store` | db_path `/opt/data/memory_store.db` | 确认 db 文件已创建、auto_extract 正常工作 |
| `auxiliary.session_search` | 全部为空 | **需要配 model/provider** 否则会话搜索不可用 |
| `auxiliary.curator` | 全部为空 | **需要配 model** 否则 curator 仅做自动清理 |
| `sessions.retention_days` | 90 | 确认是否合理 |
| `sessions.auto_prune` | false | **建议开启**，避免磁盘无限增长 |
| `memory.memory_char_limit` | 2200 | 内置记忆字符限制，确认够用 |
| `memory.user_char_limit` | 1375 | 同上 |

---

## 第二阶段：配置激活（2-3 天）

### B1：内置记忆 — MEMORY.md / USER.md

**目标**：让 Hermes 有持久的系统级记忆，重启不丢。

```
/opt/data/MEMORY.md    ← Hermes 关于如何工作的系统记忆
/opt/data/USER.md      ← 用户画像、偏好、项目上下文
```

**写入内容建议：**

```markdown
# MEMORY.md — 我的工作方式
- 用户操作系统：Windows 11 + WSL2 (Ubuntu) + Docker Desktop
- 容器目录 /opt/data 对应宿主机 C:\Users\Lsc\.hermes
- LLM 通过 host.docker.internal:11434 访问宿主 Ollama
- 默认模型：VibeThinker-3B:latest（本地）
- 主要交互渠道：WeChat iLink（gateway 运行中）
- 风格偏好：中文回复，简洁，重实效
- 休眠恢复：由宿主机 connection_persister.py 守护
```

```markdown
# USER.md — 用户画像
- 我在做一个 AI 音频处理项目（AudioVectorSystem）
- 使用 Hermes + Ollama 本地 AI 栈
- 有软件开发背景，偏好命令行操作
- 对响应速度敏感，偏好本地模型
- 夜间关机，白天持续工作
```

### B2：配置辅助模型

**关键**：session_search、curator、title_generation 等 Hermes 子系统的辅助模型全为空。当前 `VibeThinker-3B:latest` 是本地小模型，如果直接用同一个模型做 embedding/search 可能不理想。

方案选择：
- **方案 A（推荐）**：配 VibeThinker-3B 作为所有 auxiliary model（简单，同质化）
- **方案 B**：拉一个专用 embedding 模型（如 bge-m3），用于搜索/记忆
- **方案 C**：保持为空（Hermes 会 fallback 到默认 model）

### B3：Holographic 记忆确认

**测试流程**：
1. 通过 WeChat 发送 "记住：我的项目叫 AudioVectorSystem，使用 Python + FastAPI"
2. 等待 10 秒让 hermes-memory-store plugin 自动提取
3. 检查 `memory_store.db` 是否写入
4. 重启容器
5. 发送 "我的项目叫什么？"
6. **通过标准**：能正确回答 "AudioVectorSystem"

### B4：Skills 安装

Hermes skills hub 有现成 skill 可用。调研并安装有用的：
- `hermes skills install <name>` 从 hub 安装
- 优先安装：搜索增强、代码分析、系统运维相关

### B5：MCP Server 配置

**候选 MCP Server**：
- GitHub（版本管理）
- 文件系统操作（本地文件深度访问）
- 数据库查询（如果用到 SQLite）
- Playwright（浏览器自动化增强）

---

## 第三阶段：能力验证（2-3 天）

### C1：跨会话记忆验证

```
测试矩阵：
╔══════════════════════════════╤══════════════════╤══════════════╗
║ 测试场景                     │ 依赖              │ 通过标准     ║
╠══════════════════════════════╪══════════════════╪══════════════╣
║ TC-MEM-01: 记住偏好          │ MEMORY.md/USER.md │ 重启后记住   ║
║ TC-MEM-02: 记住事实          │ holographic       │ 跨会话回答   ║
║ TC-MEM-03: 更新记忆          │ holographic       │ 新值覆盖旧值 ║
║ TC-MEM-04: 会话搜索          │ session_search    │ 搜到上周内容 ║
║ TC-MEM-05: 冲突记忆          │ holographic       │ 最新优先     ║
╚══════════════════════════════╧══════════════════╧══════════════╝
```

### C2：任务执行验证

```
测试矩阵：
╔══════════════════════════════╤══════════════════╤══════════════╗
║ 测试场景                     │ 工具              │ 通过标准     ║
╠══════════════════════════════╪══════════════════╪══════════════╣
║ TC-TASK-01: 多步骤任务       │ todo              │ 按计划逐步执行║
║ TC-TASK-02: 子 agent 并发    │ delegation        │ 并行完成     ║
║ TC-TASK-03: 定时任务          │ cronjob           │ 按时触发     ║
║ TC-TASK-04: 看板管理          │ kanban            │ 增删改查     ║
║ TC-TASK-05: 跨平台消息        │ messaging         │ WeChat 收发  ║
╚══════════════════════════════╧══════════════════╧══════════════╝
```

### C3：系统集成验证

```
测试矩阵：
╔══════════════════════════════╤══════════════════╤══════════════╗
║ 测试场景                     │ 工具              │ 通过标准     ║
╠══════════════════════════════╪══════════════════╪══════════════╣
║ TC-SYS-01: Shell 执行        │ terminal          │ 容器内命令   ║
║ TC-SYS-02: 文件操作          │ file              │ 读写卷目录   ║
║ TC-SYS-03: 代码执行          │ code_execution    │ Python 运行  ║
║ TC-SYS-04: 网页浏览          │ browser           │ 截图 + 内容  ║
║ TC-SYS-05: 网络搜索          │ web               │ 返回结果     ║
╚══════════════════════════════╧══════════════════╧══════════════╝
```

---

## 第四阶段：缺陷修复与加固（持续）

### D1：已知问题

| 缺陷 | 严重度 | 状态 |
|------|--------|------|
| 休眠断连 | **高** — WeChat 中断 | ✅ **已修复**（connection_persister + wsl2-network-reset） |
| cron 任务 iLink rate limited | **中** — 定时任务失败 | ⚠️ 需关注（iLink 限流，非 Hermes 问题） |
| auxiliary model 未配置 | **中** — session_search/curator 不可用 | ⏳ 待配置 |
| MEMORY.md/USER.md 不存在 | **中** — 内置记忆未用 | ⏳ 待创建 |
| memory_store.db 待确认 | **中** — 长期记忆可能未生效 | ⏳ 待验证 |
| 无 skills/plugins/MCP | **低** — 能力可扩展但未扩展 | ⏳ 按需配置 |

### D2：持续监控

```bash
# 每日检查
hermes sessions stats                # 会话量
hermes memory status                 # 记忆系统
hermes cron list                     # 定时任务
hermes tools list                    # 工具状态

# 从宿主机
python connection_persister.py --check  # 连接状态
docker logs hermes --tail 30           # 容器日志
```

---

## 熔断与迭代规则

### 测试失败响应

```
P0 功能测试失败
  ├── 第 1 次失败 → 记录缺陷，分析根因
  ├── 第 2 次失败 → 阻塞该模块，切换优先级
  ├── 第 3 次失败 → 全量回退配置，标记为 "不支持"
  └── 数据丢失/损坏 → 立即熔断
```

### 优先级覆盖原则

```
数据完整性 > WeChat 可用性 > 记忆准确率 > 任务完成率 > 功能丰富度
```

### 版本标记

| Tag | 含义 |
|-----|------|
| `baseline` | 当前状态（配置审计前） |
| `v1-configured` | 所有配置项就绪（B 阶段完成） |
| `v1-verified` | 核心测试矩阵全绿（C 阶段完成） |
| `v1-hardened` | 所有已知缺陷修复或降级 |

---

## 时间线

```
Day 1-2:  A1 审计 + A2 配置盲区确认
Day 3-4:  B1 MEMORY.md/USER.md + B3 记忆验证
Day 5-6:  B2 辅助模型配置 + B4/B5 Skills/MCP
Day 7-9:  C1-C3 全量测试矩阵
Day 10+:  D1 缺陷修复 + D2 监控上线
         └── 切换日常使用，按需迭代
```

---

> **核心原则**：先验证 Hermes 已有的，只补它没有的。不重复造轮子。
