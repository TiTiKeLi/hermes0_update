 ---
 name: git-version-control
 description: Hermes Git 版本管理 — 数据分类体系、.gitignore 排除规则、首次推送审计、定时同步机制。适用于任何 Docker 化 AI Agent 项目的版本控制。
 category: workflow
 platforms: [windows]
 related_skills: [config-unification, skill-creation-rules]
 triggers:
   keywords:
     - 版本管理
     - GitHub
     - git
     - 备份
     - 上传
     - 同步
     - 仓库清理
     - .gitignore
     - gitignore
     - 推送
     - commit
     - 仓库审计
     - 排除规则
 ---
 
 # Git Version Control — Hermes Git 版本管理 v1
 
 ## 核心问题
 
 Hermes 项目目录包含大量不同类别的文件。不加区分地全部推送到 GitHub 会导致：
 
 1. **密钥泄露**：.env（API keys）、auth.json 明文在公网暴露
 2. **仓库臃肿**：数据库文件（state.db 58MB）、缓存、日志、定时任务输出（260+ 文件）
 3. **数据泄露**：sessions/、memories/、incoming/ 包含用户对话记录
 4. **重复内容**：versions/ 目录与根目录的 gui.py/gui.html 重复
 5. **运行时状态**：gateway_state.json、ticker_heartbeat 等每时每刻都在变，commit 历史会被刷屏
 
 ## 数据分类体系
 
 所有文件按 6 个维度分类，每个维度决定"能不能上传"：
 
 | 类别 | 特征 | 能不能上传 | 原因 |
 |------|------|-----------|------|
 | 数据库数据 | *.db, *.db-wal, *.db-shm, *.sqlite | ❌ 不能 | 包含运行时数据、对话记录 |
 | 密钥 | .env, auth.json, *key*, *token*, *secret* | ❌ 不能 | API keys 明文，公网暴露即被盗 |
 | 缓存 | __pycache__/, cache/, *.pyc, *.json 大文件 | ❌ 不能 | 可重新生成，上传无意义 |
 | 运行时数据 | sessions/, memories/, incoming/, *.log | ❌ 不能 | 用户隐私，且持续变化 |
 | 备份 | backups/, *.bak, versions/*.bak | ❌ 不能 | 占用空间，无版本价值 |
 | 定时任务输出 | cron/output/, cron/ticker_* | ❌ 不能 | 运行时日志，每分钟都可能变化 |
 | 配置与代码 | config.yaml, Dockerfile, docker-compose.yml | ✅ 可以 | 核心版本化物件 |
 | 技能 | skills/**/*.md, skills/**/*.py | ✅ 可以 | 自定义知识和工作流 |
 | 脚本 | *.ps1, *.py, *.sh（非缓存） | ✅ 可以 | 工具脚本和自动化 |
 | 文档 | CONTEXT.md, MEMORY.md, USER.md, README.md | ✅ 可以 | 项目上下文（注意 MEMORY.md 可能含敏感信息） |
 
 ## 审计流程
 
 ### 首次推送前的审计
 
 每次初始化 git 仓库或首次推送到远程时，执行以下检查：
 
 ```
 Step 1: 列出所有未被 .gitignore 排除的文件
   git status --short
 
 Step 2: 逐条审阅每个文件是否符合上传标准
   □ 是否包含 API key、token、密码？
   □ 是否是数据库或数据文件？
   □ 是否是缓存或临时文件？
   □ 是否是运行时状态（持续变化）？
   □ 是否是备份（有 *.bak 后缀）？
   □ 根目录和 versions/ 目录是否有重复？
   □ 是否是测试/调试单次脚本？
 
 Step 3: 对不符合条件的文件
   □ 添加到 .gitignore
   □ 从跟踪中移除: git rm --cached <file>
 
 Step 4: 提交并推送
   git add -A
   git commit -m "chore: 描述本次操作"
   git push origin master
 ```
 
 ### 定时审计（配合每小时同步）
 
 每小时同步脚本 `git-sync.ps1` 会自动：
 1. `git status --short` 检查是否有变更
 2. 有变更则 `git add -A && git commit && git push`
 3. 无变更则静默退出
 
 定时任务注册命令：
 ```powershell
 schtasks /create /tn HermesGitSync `
   /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"$env:USERPROFILE\.hermes\git-sync.ps1\"" `
   /sc hourly /f
 ```
 
 ## .gitignore 模板
 
 ```gitignore
# === 数据库 ===
*.db
*.db-wal
*.db-shm
*.sqlite
*.sqlite3

# === 缓存 ===
__pycache__/
*.pyc
cache/
audio_cache/
image_cache/
context_length_cache.yaml
models_dev_cache.json

# === 日志 ===
*.log
logs/
healthcheck.log

# === 数据目录 ===
sessions/
memories/
incoming/
weixin/

# === 备份 ===
backups/
*.bak

# === 密钥 ===
.env
auth.json
auth.lock
wechat_qr.json
wechat_qr.png

# === 系统运行时状态 ===
.connection_state
gateway_state.json
gateway.lock
gateway.pid
processes.json
channel_directory.json
cron/ticker_*
research/heartbeat_last.json

# === 定时任务输出 ===
cron/output/

# === 临时文件 ===
*.lock
*.pid

# === 大型文件 ===
*.zip
*.tar.gz

# === 版本历史（重复内容）===
versions/

# === 测试文件 ===
test_embed.py
_test_ds.py

# === OS 文件 ===
Thumbs.db
.DS_Store
Desktop.ini
```
 
 ## 本次实例复盘
 
 初始化推送时，380 个文件被跟踪，审计后发现以下违规：
 
 | 违规文件 | 数量 | 类型 | 修复 |
 |---------|------|------|------|
 | cron/output/ | 260 | 定时任务输出 | git rm --cached + 加入 .gitignore |
 | cron/ticker_* | 2 | 运行时状态 | 同上 |
 | research/heartbeat_last.json | 1 | 运行时状态 | 同上 |
 | test_embed.py | 1 | 测试文件 | 同上 |
 | versions/*.bak | 1 | 备份文件 | 同上 |
 | cron/output/ 日志 | 260 | ⚠️ 已上传后才发现 | 后续提交清理，GitHub 历史中仍可回溯 |
 
 **教训**：.gitignore 必须在首次 git add 之前就写好。文件一旦提交到 GitHub，即使后续删除，历史记录中仍然存在。
 
 ## 边界条件
 
 ### 入口条件
 - 首次为项目初始化 git 仓库
 - 发现仓库中有不应存在的文件
 - 需要设置定时同步到远程
 - 项目结构变化后需要更新排除规则
 
 ### 出口条件
 - .gitignore 覆盖所有 6 类禁止上传的文件
 - 已运行一次 git rm --cached 清理历史
 - 定时同步脚本已创建并注册
 
 ## 相关参考
 
 - [.gitignore 实例](../../../.gitignore) — 本项目当前使用的 .gitignore
 - [git-sync.ps1](../../../git-sync.ps1) — 定时同步脚本
 - [config-unification](../../architecture/config-unification/SKILL.md) — 配置统筹方法论

## 数据安全审计体系

### 三层防护

Layer 1: .gitignore（被动防御）
  22 类排除模式，阻止 git add 误操作

Layer 2: pre-commit hook（主动拦截）
  每次 git commit 前扫描 staged 文件
  脚本: data-security-audit.ps1
  hook: pre-commit-hook.bat → 复制到 .git/hooks/pre-commit

Layer 3: 定时同步守卫（自动防护）
  自动推送前也执行审计，不通过则不提交

### 审计规则

文件名匹配（14 种模式）:
  数据库(*.db) 日志(*.log *.jsonl) 会话(session_*)
  请求转储(request_dump_*) 备份(*.bak) 密钥(.env auth.json)
  压缩包(*.zip) 音频(*.mp3) 编译缓存(*.pyc) 二进制(tirith)

内容密钥扫描:
  检查 config.yaml 等文件中的 api_key/password/token 非空值

### 安装 hook
  copy pre-commit-hook.bat .git\hooks\pre-commit

### 手动全量审计
  .\data-security-audit.ps1 -FullScan

### Gitleaks 对比验证结果

| 维度 | 我们的系统 | Gitleaks (行业标准) |
|------|-----------|-------------------|
| 文件类型扫描 | 22种模式 | ✅ 内置 |
| 密钥模式数 | ~8种 | 150+种 |
| 熵检测 | ❌ | ✅ |
| 全量历史扫描 | ❌ | ✅ |
| 9 commits 全量结果 | — | **无泄漏** ✅ |

**结论**：Gitleaks 验证了我们当前的安全状态是无泄漏的。
但我们的自定义脚本缺少 150+ 种密钥模式和熵检测，建议保持 Gitleaks 作为第二道防线。

### 当前安全架构（三层 + 行业工具）

`
Layer 1: .gitignore
  22类排除模式

Layer 2: data-security-audit.ps1
  文件名 + 内容密钥扫描

Layer 3: Gitleaks
  150+模式 + 熵检测
  
Commit 触发 → Layer 1 → Layer 2 → Layer 3 → 允许提交
                                              ↓
                                          失败 → 阻止
`

### 安装要求

Gitleaks 已安装到: C:\Users\Lsc\AppData\Local\gitleaks\gitleaks.exe
首次安装后需要管理员权限运行一次来为 git hooks 注册路径。
