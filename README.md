# Hermes Agent — 个人 AI 基础设施

> 基于 Docker 的 Hermes AI Agent 部署，运行在 Windows 11 + WSL2 环境。
> 集成 WeChat 交互、技能体系、四层记忆架构、自动备份。

---

## 项目概述

本仓库是 Hermes AI Agent 的完整部署配置。Hermes 运行在 Docker 容器中，通过 WeChat 与用户交互，具备技能扩展、记忆管理、自动维护等能力。

### 核心能力

| 能力 | 说明 |
|------|------|
| 容器化部署 | Docker Compose + bind mount 持久化 |
| WeChat 交互 | iLink 网关, 中文精简回复格式 |
| 技能体系 | 30+ 技能, 触发器驱动自动加载 |
| 记忆架构 | 四层(L1-L4): 原始→事实→温缓存→热缓存 |
| 安全审计 | Gitleaks + data-security-audit + pre-commit hook |
| 数据持久化 | bind mount 到宿主机, 数据不丢失 |
| GitHub 同步 | 本地 commit, 手动推送 |

---

## 目录结构

```
├── config.yaml            Hermes 主配置
├── docker-compose.yml     容器编排
├── Dockerfile             镜像构建
├── .env                   环境变量（密钥）
├── .gitignore             排除规则（22 类）
│
├── skills/                技能体系（30+）
│   ├── architecture/      架构类
│   ├── behavior/          行为类
│   ├── memory/            记忆类
│   ├── security/          安全类
│   ├── thinking/          思维类
│   ├── workflow/          工作流类
│   └── meta/              元类
│
├── scripts/               工具脚本
├── hooks/                 Hermes 钩子系统
├── cron/                  定时任务
├── gateway/               网关配置
│
├── sessions/              会话记录（不跟踪）
├── memories/              记忆数据（不跟踪）
├── logs/                  日志（不跟踪）
├── backups/               备份（不跟踪）
│
├── MEMORY.md              Agent 工作记忆
├── USER.md                用户画像
├── SOUL.md                Agent 人格定义
├── CONTEXT.md             项目上下文
└── ARCHITECTURE.md        架构总览
```

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.0 baseline | 2026-07-25 | 初始配置, Docker 网络修复, 数据持久化 |
| v0.1 | 2026-07-25 | 技能体系审计, .gitignore 排除规则, Gitleaks 集成 |
| v0.2 | 2026-07-25 | 配置统筹方法论, 故障回溯入口 |
| v0.3 | 2026-07-25 | 创建 15+ 新技能, 质量门禁, 开发循环 |
| v0.4 | 2026-07-25 | 项目生命周期管理, UX 审计, 依赖追踪 |
| v0.5 | 2026-07-26 | WeChat 回复格式精简, 中文强制输出 |
| v0.6 | 2026-07-26 | 四层记忆架构 L1-L4 设计定稿 |
| v0.7 | 2026-07-26 | 存储架构, 版本策略, 原子写入 |
| current | 2026-07-26 | 钩子系统, 触发器索引, 自动维护 |

---

## 快速开始

```bash
# 启动 Hermes
docker compose up -d

# 查看日志
docker logs hermes -f

# 检查技能加载
docker exec hermes hermes skills list

# 执行安全审计
./data-security-audit.ps1 -FullScan
```

---

## 版本管理规则

```
□ 新功能 → git add <specific files> → git commit → git push
□ 运行数据（*.db, sessions/, logs/）→ 不跟踪
□ 密钥（.env, auth.json）→ .gitignore 排除
□ 个人技能 → 跟踪, 技能注册表同步更新
□ 定时同步 → git add -u（仅已跟踪文件）
```

---

## 依赖

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker Desktop | 27.4.0 | 容器运行时 |
| Hermes | latest | AI Agent |
| Gitleaks | 8.18.2 | 密钥扫描 |
| Ollama | latest | 本地模型（可选） |
| WeChat | — | 交互前端 |

---

## 许可证

Nous Research Hermes 派生项目。详见 LICENSE 文件。
