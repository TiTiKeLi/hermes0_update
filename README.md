# Hermes Agent — 个人 AI 基础设施

> 基于 Docker 的 Hermes AI Agent 部署配置，运行于 Windows 11 + WSL2。
> GitHub 版本仅包含核心配置和技能定义。

---

## 仓库内容

本仓库跟踪的是 Hermes Agent 的**配置和技能定义**，不包含运行时数据、密钥、缓存。

### 核心配置

| 文件 | 说明 |
|------|------|
| `config.yaml` | Hermes 主配置 |
| `docker-compose.yml` | Docker 容器编排 |
| `Dockerfile` | 容器镜像构建 |
| `.gitignore` | 排除规则（22 类） |

### 技能体系（36 个）

| 类别 | 技能数 | 说明 |
|------|--------|------|
| architecture | 5 | 配置统筹, 工具治理, 记忆架构, 桥接协作 |
| behavior | 5 | 小模型模式, 记忆反馈, 偏好学习, 微信格式, 中文格式 |
| memory | 2 | 分层同步, 压缩归档 |
| security | 2 | 安全下载, 下载门卫 |
| thinking | 2 | 深度需求分析, 结构化推理 |
| workflow | 17 | 工作流编排, 外部适配, 版本管理, 质量门禁等 |
| meta | 1 | 技能创建规则 |
| finance | — | 本地仅存 |
| misc | 1 | 看板修改器 |

### 脚本与工具

| 目录 | 说明 |
|------|------|
| `scripts/` | 工具脚本（原子写入, 容量监控, 死循环检测等） |
| `hooks/` | Hermes 钩子系统引擎 |
| `cron/` | 定时任务配置 |

### 安全

| 文件 | 说明 |
|------|------|
| `.gitignore` | 22 类排除模式（数据库/密钥/缓存/会话/日志） |
| `data-security-audit.ps1` | 安全审计脚本 |
| `pre-commit-hook.bat` | git pre-commit 钩子 |
| `gitleaks-report.json` | Gitleaks 扫描报告 |

---

## 版本历史

| 标签 | 说明 |
|------|------|
| `memarch-v0.0` | 版本管理框架 baseline |
| `memarch-v0.1` | 脚本修复 + cron 注册 |
| `v0.2-v0.7` | 技能体系 + 记忆架构逐步迭代 |
| `current` | HEAD |

---

## 本地部署（不包含在本仓库中）

以下内容仅在本地环境存在，已通过 `.gitignore` 排除：

```
codex-bridge/         桥接系统（请求/响应/状态机）
projects/             项目计划文档
sessions/             会话记录
memories/             记忆数据
logs/                 运行日志
backups/              备份
*.db                  数据库文件
.env / auth.json      密钥
```

---

## 使用

```bash
git clone <repo>
# 复制 .env.example 到 .env 并配置密钥
docker compose up -d
docker exec hermes hermes skills list
```

---

## 依赖

| 组件 | 用途 |
|------|------|
| Docker Desktop | 容器运行时 |
| Hermes | AI Agent |
| Gitleaks | 密钥扫描 |
| WeChat | 交互前端 |

---

## 许可证

Nous Research Hermes 派生项目。

