---
name: secure-download
description: 下载安全门卫 —— 来源验证 + 内容扫描 + 决策 + 归档的全流程安全保障，覆盖 secure-download 原则 + download-gate 过程
category: security
conditions:
  requires_toolsets:
    - file
    - terminal
    - web
platforms: [linux]
related_skills:
  - external-adaptor
  - tool-governance-v2
triggers:
  keywords:
    - 安全下载
    - 下载文件
    - 下载安全
    - 下载检查
    - 下载验证
    - secure download
    - download check
    - 文件下载
    - 安全检查
    - 下载防护
---

# Secure Download — 下载安全门卫

每次从外网（GitHub、第三方CDN、未知URL等）下载内容到 Hermes 时，必须触发此技能。

本技能 = merge of `secure-download`（原则层）+ `download-gate`（过程层）。

---

## ⚡ 强制范围

本门卫覆盖以下所有入口：
1. **`external-adaptor`** — Step 0 强制加载本 skill，不满足条件即中止
2. **`cronjob(script=…)`** — 任何通过脚本抓取外部内容的 cron，创建前必须先校验
3. **`write_file`** — 后置钩子自动触发（通过 `tool-governance-v2`）
4. **`skill_manage(action='create')` / skill 下载** — 通过 `external-adaptor` 触发
5. **用户直接粘贴内容** — 在 `external-adaptor Step 0` 中临时写入 `/tmp/gate_pending_content` 后扫描

---

## 1. 边界条件

### 入口条件

- 需要从外部源下载文件
 - 下载前需要安全检查
 - 文件来源不可信

### 跳过条件（一条即跳过）
- [ ] 内容来源是 `trusted.json` 白名单中的已知路径
- [ ] 用户明确说 `--skip-gate`（含风险和后果确认）
- [ ] 来源是本地已有文件（已在 `/opt/data/` 内部）且未修改

### 中止条件（执行中，一条即停）
- [ ] 来源验证失败（域名未知 / 证书过期 / 404）
- [ ] 内容扫描发现硬编码凭据（API_KEY / TOKEN / SECRET 等且非变量名）
- [ ] 内容扫描发现恶意代码（eval/exec 动态执行、base64 解码后执行、反向shell）
- [ ] 用户回复"不下载" / "算了"

---

## 2. 决策矩阵

| 场景 | 行动 | 产出 |
|------|------|------|
| 来源是 github.com 知名仓库 | 快速验证 → 自动通过 | 通过 + 写入 trusted.json |
| 来源是 pypi.org / npmjs.com | 检查完整性哈希 | 通过 + 记录 |
| 来源是未知域名 | 问用户"确认下载？" + 内容预检 | 用户确认后入 trusted.json |
| 来源内容含可疑模式 | 隔离 + 列出危险行 | 隔离 + 告警 |
| 内容是纯文本/文档 | 无扫描直接通过 | 通过 |

---

## 3. 原子步骤

### Step 0: 来源验证

**操作**：
1. 判断来源类型：URL / 文件路径 / 聊天粘贴
2. URL → 检查域名：打标签（github.com / pypi.org / npmjs.com / 其他）
3. Docker 容器检测：`which curl git` → 没有 curl/git/jq → 用 Python urllib 替代
4. 聊天粘贴内容 → `write_file` 到 `/tmp/gate_pending_content`
5. 检查容器的 SSL/TLS 证书缺失（Python urllib 失败时降级）
6. 如果是 GitHub 仓库 → 优先 `curl -L -o <name>.zip` + `unzip`（比 git clone 快）

**验证**：域名可解析 / 文件可读 / 内容非空

**产出**：来源类型 + 域名标签 + 内容临时路径

---

### Step 1: 内容扫描

**操作**：
1. 扫描凭据泄露模式：
   `grep -inE 'api_key|token|secret|password|private_key' <file>`
2. 扫描恶意执行模式：
   `grep -inE 'eval\(|exec\(|base64.*decode|socket\.' <file>`
3. 扫描外发网络请求（非标准域名）
4. 对每条匹配：记录行号 + 内容摘要到 `/opt/data/download_gate/scan_report_<timestamp>.md`

> ⚠️ 扫描模式有假阳性（session JSON 日志和自身代码库常被误报）。参考 `references/scan-tooling.md` 了解调优方案。

**验证**：`read_file("scan_report_*.md")` → 确认扫描完整

**产出**：扫描报告 + 危险/安全结论

---

### Step 2: 决策

**操作**：
1. ✅ 无任何危险模式 → 自动通过
2. ⚠️ 发现变量名级疑似（`TOKEN` 作为参数名，无实际值） → 警告但可继续
3. ❌ 发现实际凭据或恶意代码 → 中止，拒绝写入
4. 用户确认开关：`--skip-gate` → 强制通过（记录到操作日志）

**验证**：决策结论明确（通过 / 警告通过 / 拒绝）

**产出**：决策结果

---

### Step 3: 记录归档

**操作**：
1. 通过的内容 → 写入 trusted.json：
```json
{
  "source": "<url/路径>",
  "file_hash": "<sha256>",
  "passed_at": "<ISO timestamp>",
  "verified_by": "secure-download"
}
```
2. 拒绝的内容 → 写入 `/opt/data/download_gate/blocked/blocked_<timestamp>.json`
3. 更新 `state_registry`：注册 `download-gate` 工具状态

**验证**：`read_file("trusted.json")` → 确认新条目存在

**产出**：trusted.json 条目 / blocked 记录

---

## 4. 工具/Skill 联动表

| 步骤 | 读取 | 写入 | 依赖的 skill | 触发条件 |
|------|------|------|-------------|---------|
| Step 0 | 外部来源 / trusted.json | `/tmp/gate_pending_content` | `external-adaptor` | 来源提供 |
| Step 1 | 临时内容文件 | `scan_report_*.md` | — | 内容已获取 |
| Step 2 | 扫描报告 | — | — | 扫描完成 |
| Step 3 | trusted.json | trusted.json / blocked/ | `tool-governance-v2`（注册） | 决策完成 |

---

## 5. 反馈回路

### 5.1 每步文件验证
每个 `write_file` 后必须 `read_file` 回读

### 5.2 通过/拒绝记录
- 通过的来源写入 trusted.json（持久化，cron watcher 也会读）
- 拒绝的来源写入 blocked/ 目录（含完整扫描报告），供审计

### 5.3 降级/死路标记
- 连续 3 次扫描失败（脚本报错）→ 标记 `secure-download` 为 degraded
- 白名单 trusted.json 损坏 → 视为空白名单，所有下载需显式批准
- external-adaptor Step 0 检测到 degraded → 提醒用户手动审批

### 5.4 回复固化
每次 gate 操作输出摘要：
```
🔒 Secure Download: <来源>
   ├─ 来源: <域名> [可信/未知]
   ├─ 扫描: ✅安全 / ⚠️警告 / ❌拒绝
   └─ 决策: 通过 / 拒绝 / 需确认
```

### 5.5 迭代上下文
写入 `/opt/data/download_gate/state.json`：
```json
{
  "last_check": "<ISO timestamp>",
  "total_passed": N,
  "total_blocked": N,
  "trusted_count": M,
  "status": "active|degraded",
  "trusted_json_valid": true|false
}
```

---

## 容器环境注意事项

### SSL/TLS 证书缺失
- 容器可能缺少系统 CA 证书（`apt-get install -y ca-certificates` 可修复）
- Python urllib 在缺少 CA 证书时验证失败 → 安全降级方案：
  ```python
  import ssl, urllib.request
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE  # 容器内无 CA 时的必要降级
  urllib.request.urlopen(url, context=ctx)
  ```
- ⚠️ **降级是合理的**：github.com 是可信域名，容器内 CA 缺失是环境问题，非传输安全问题

### 工具缺失预判
- `curl`, `git`, `jq` 可能未预装
- `apt-get install` 可能被 `dpkg` 锁定 → 用 Python 替代方案
- 下载前先检测：`which curl git` → 没有则用 Python 方案

### 安全等级
1. **来源可信度**（域名、star数、许可证、活动时间）
2. **内容静态扫描**（凭据泄露、恶意模式）
3. **传输层安全**（SSL 验证是锦上添花，非必要条件）

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

