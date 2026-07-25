---
name: external-adaptor
description: 外部项目/Skill 下载→拆解→架构映射→重组→集成→测试全流程管道
category: workflow
conditions:
  requires_toolsets:
    - terminal
    - file
    - web
platforms: [linux]
related_skills:
  - secure-download
  - github-discover
  - skill-creation-rules
  - caveman
  - memory-compactor
  - meta-orchestrator
triggers:
  keywords:
    - 外部项目
    - 外部集成
    - 引入外部
    - 下载项目
    - 外部适配
    - external adapt
    - import project
    - 外部引入
    - 外部适配
    - 外部代码
    - 集成外部
---

# External Adaptor v1 — 外部项目/Skill 适配管道

从外部（GitHub、博客、文档等）获取的项目或 skill，不能被直接扔进来用。
必须经过**拆解→架构映射→重组→集成→测试**，贴合已有架构和约定后再落地。

---

## 1. 边界条件

### 入口条件

- 需要将外部项目集成到 Hermes
 - 外部项目需要拆解和适配
 - 需要下载并分析外部代码

### 跳过条件（一条即跳过）
- [ ] 该功能/模式已在我们的 skill 或项目中存在
- [ ] 用户明确说"直接下载用，不用改"
- [ ] 来源连续 2 次获取失败且用户无法提供替代方式
- [ ] 内容分析后判定：全是专有逻辑，无通用模式可提取

### 中止条件（执行中，一条即停）
- [ ] 用户切换话题或插入新指令
- [ ] 拆解后发现核心依赖与 Hermes 环境不兼容（如需要 Node.js 但我们只有 Python/Node）
- [ ] 重组时发现需要改 core Hermes 配置文件（非用户级操作）
- [ ] 连续 2 个测试步骤失败

---

## 2. 决策矩阵

| # | 场景 | 行动 | 工具链 | 产出 |
|---|------|------|--------|------|
| 0 | GitHub 仓库含完整 skill/项目 | 全链路：下载→拆解→映射→重组→测试 | `secure-download` + `terminal` + `read_file` + `skill_manage` | 集成的 skill / 项目文件 |
| 1 | 单文件/脚本（.py/.sh） | 提取核心模式→映射到 Hermes→适配 | `read_file` + `patch` + `write_file` | 重写后的文件或更新已有 skill |
| 2 | 博客/文章/文档描述概念 | 提取设计思想→按 skill-creation-rules 创建 | `read_file` + `skill_manage(create)` | 新 skill + SKILL_REGISTRY 条目 |
| 3 | 用户口头描述模糊想法 | 追问→设计·映射→创建 | `clarify` + `skill_manage` | 新 skill |
| 4 | 来源不可达 | 记录待办→告知用户等网络恢复 | `write_file`→`research/topics/<slug>/pending.txt` | 等待队列条目 |
| 5 | 拆解后发现与已有 skill 重叠 | 不新建，提取有用模式更新已有 skill | `skill_manage(patch)` + `references/` | 更新后的已有 skill |
| 6 | **批量技能仓库**（如 superpowers-zh 的 20+ skill） | 先做 **Triage 分拣**（见 Step 0a），再分批进入主流程 | `skills_list` + `skill_view` + 分类表 | triage 报告 + 分桶（创建/合并/跳过） |
| 7 | VibeThinker-3B 相关的外部 content | Caveman 格式适配 | `caveman` + `memory_compactor_vibe.py` | 3B 可处理的 caveman 格式 |

---

## 3. 原子步骤

### Step 0: 来源获取 + ⚡下载门卫安全检查（强制）

**输入**：用户的来源描述（URL/文件/概念）
**工具**：`secure-download` skill + `terminal` / `read_file`
**操作**：
1. 首次运行本 skill 时，自动加载 `secure-download` skill 并确认其边界条件
2. ⚡下载门卫 — 每次下载前强制执行：
   - URL 来源 → 调用 `secure-download` Step 0（来源验证）+ Step 1（内容扫描）
   - 本地文件路径 → 调用 `python3 /opt/data/scripts/download_gate.py check <path>`
   - 用户粘贴内容 → `write_file` 到临时路径后调用 `download_gate.py scan`
3. 门卫决策结果：
   - ✅ 通过 → 继续（自动写入 `trusted.json`）
   - ⚠️ 警告通过 → 记录后继续，但最终报告标注
   - ❌ 拒绝 → **流程中止**，返回隔离报告给用户
4. 如果来源是 URL → 加载 `secure-download` skill 补充执行安全检查（两层校验）
5. 如果是 GitHub 仓库 → 优先 `git clone --depth 1`，注意陷阱：
   - ⚠️ 大型仓库（>3000 files）60s terminal 超时内无法完全签出 → 需要额外 `cd <dir> && git restore --source=HEAD :/`
   - ⚠️ 更可靠方案：`curl -L -o <name>.zip "https://github.com/owner/repo/archive/refs/heads/main.zip"` + `unzip`（单流下载，比 git 协议快）
   - ⚠️ 不要用 `git clone` 对需认证的仓库（会弹 "could not read Username"），选公开仓库
   - ⚠️ 搜索 API（`api.github.com/search/...`）响应慢（>10s），单仓库查询快（<5s）→ 优先用已知 URL 而非搜索
6. `download_gate.py trust` 不支持目录级别操作（`IsADirectoryError`）→ 信任文件用 `python3 /opt/data/scripts/download_gate.py trust <file> --source "..."`，信任整个目录用 `scan --auto-write`
7. 如果容器无外网 → 告知用户，写入 pending 队列
8. 无论来源类型，创建分析工作区：`research/external/<slug>/`

**验证**：
```
# 门卫通过后才能进入后续步骤
python3 /opt/data/scripts/download_gate.py check <path> → 输出 ✅
read_file(path=刚下载的文件) → 确认内容非空
如果 clone 仓库 → ls <克隆目录> → 确认有文件
```

---

### Step 0a: 批量技能仓库 Triage 分拣（场景 6 专用）

**入口条件**：来源是含 5+ 个可独立评估的 skill/模块（如 superpowers-zh 的 20 个独立 skill）
**工具**：`skills_list` + `skills_list()` → 获取已有 skill + `skill_view`（抽查待评估 skill）
**产出**：`research/external/<slug>/triage-report.md`

**操作**：

1. **全表扫描** — 列出仓库中所有 skill，列名 + 1 句描述
2. **快速分类** — 对每个 skill，判断：

   | 标签 | 含义 | 后续行动 |
   |------|------|---------|
   | **CREATE** | 高价值，我们无等价skill | 走完整管道（Step 1-6） |
   | **MERGE** | 有价值但内容落在已有skill范畴 | 读取已有skill → `patch` 吸收关键部分 |
   | **SKIP** | 项目特化、已过时、优先级低 | 仅记录到 triage 报告 |
   | **REFERENCE** | 资料类，无步骤结构 | 写为引用文档到关联 skill 的 `references/` |

3. **重叠检查** — 对 CREATE/MERGE 候选，用 `skills_list()` 确认与已有 skill 不重复：
   - 如果已有 skill 名字不同但 >50% 内容重复 → 降级为 MERGE
   - 如果已有 skill 名字相同（如 `dispatching-parallel-agents` 已在我们的系统中）→ 对比版本差异，只吸收增量
4. **分桶** — 输出分类表写入 `triage-report.md`：
   ```markdown
   # Triage Report: <仓库名>
   ## CREATE (N 个)
   | 名 | 理由 | 预估工作量 |
   |----|------|-----------|
   
   ## MERGE (N 个)
   | 名 | 目标 skill | 吸收内容 | 预估工作量 |
   
   ## SKIP (N 个)
   | 名 | 理由 |
   
   ## REFERENCE (N 个)
   | 名 | 目标 skill 的 references/ |
   ```
5. **优先级排序** — CREATE 和 MERGE 按价值/工作量比排序，先做高 ROI 的

**验证**：
```
read_file path="triage-report.md" → 所有 skill 均已分类（无未分类条目）
skills_list() → CREATE 候选确认不与已有 skill 重叠
SKIP 条目的理由合理（不因懒跳过，而是因不重要跳过）
```

---

### Step 1: 四维拆解（附录 A-D 内联）

**输入**：原始源代码 / 文档
**产出**：`research/external/<slug>/` 下 2~4 个分析文件

四维拆解的方法论已内联为本 skill 的附录 A-D（由原先独立的 `functional-decomp` / `arch-decomp` / `interface-decomp` / `dataflow-decomp` 合并而来）。

**操作**：

1. **功能拆解** → 按**附录 A** 步骤执行
   - 产出：`research/external/<slug>/functions.md`
2. **架构拆解** → 按**附录 B** 步骤执行（需 functions.md）
   - 产出：`research/external/<slug>/arch-map.md`
3. **接口拆解** → 按**附录 C** 步骤执行（需 functions.md）
   - 产出：`research/external/<slug>/interface.md`
4. **数据流拆解** → 按**附录 D** 步骤执行（需 functions.md + interface.md）
   - 产出：`research/external/<slug>/dataflow.md`

**精简模式**（单文件/简单脚本 → 跳过附录 B+D，只跑 A+C）

**验证**：
```
read_file(path="functions.md") → 功能清单完整
read_file(path="interface.md") → 接口映射不空
如果跑了附录 B → arch-map.md 有 Hermes 映射表
如果跑了附录 D → dataflow.md 有数据路径
```

---

### Step 2: 架构映射 → 外部 vs 我们的

**输入**：disassembly.md
**工具**：`skill_view`（查看相关已有 skill）+ `read_file` + `write_file`
**产出**：`research/external/<slug>/mapping.md`

**操作**：
1. 加载已有技能清单：`skills_list()` → 列出所有 skill
2. 外部模式 → 内部映射表：
   ```
   | 外部模式 | 我们的对应 | delta（差距） | 处理方式 |
   |----------|-----------|---------------|----------|
   | CLI 入口 | 无（Hermes 是 chat-based） | 无 CLI 生态 | 拆为 tool 函数 |
   | Config 类 | skill YAML frontmatter | 字段映射关系 | 转 skill 格式 |
   | 事件循环 | cron + 周期脚本 | 需要包裹成 no_agent | 创建 cron job |
   | ... | ... | ... | ... |
   ```
3. 决策：每个外部模式如何落地
   - `引用` → 已有完全对应，更新 references/
   - `适配` → 需要小改，写适配代码
   - `重新设计` → 外部概念好但实现不匹配，按 skill-creation-rules 重写
   - `废弃` → 不相关的模式
4. 写入 mapping.md

**验证**：
```
read_file(path="mapping.md") → 每个外部模式都有决策
无 "待定" 状态
```

---

### Step 3: 重组 → 适配为我们的格式

**输入**：mapping.md
**工具**：`write_file` + `patch` + `skill_manage(create/patch)`
**产出**：重组后的文件 / skill

**操作**：
1. 按 mapping.md 的决策逐条实现：
   - **转 skill**：如果外部文件是一个完整功能 → 按 `skill-creation-rules` 的 5 节结构创建新 skill
     - 必须包含：边界条件、决策矩阵、原子步骤、工具链映射、反馈回路
     - 创建后更新 `SKILL_REGISTRY.yaml`
   - **更新已有 skill**：`skill_manage(action='patch', ...)` 更新已有 skill 的内容
   - **写工具脚本**：如果外部工具需要 cron 或 no_agent 运行 → 写到 `/opt/data/scripts/`
   - **写引用文档**：如果是参考资料/设计模式 → 写到关联 skill 的 `references/` 下
2. 对每个操作：写文件 → `read_file` 回读确认

**验证**：
```
每条决策都落地了对应产出
read_file 回读确认每条产出内容完整
```

---

### Step 4: 集成 → 关联已有体系

**输入**：重组后的文件
**工具**：`read_file`（已有 skill）+ `patch`（更新关联/引用）
**产出**：集成验证清单

**操作**：
1. 如果创建了新 skill → 检查与已有 skill 的关联关系：
   - 在 `SKILL_REGISTRY.yaml` 更新 `related` 字段（新 skill 和已有 skill 都更新）
   - 在已有 skill 的 `related_skills` 中添加新 skill
2. 如果更新了已有 skill → 验证其他依赖该 skill 的组件是否需要适配
3. 如果写了脚本文件 → 验证脚本路径在对应 cron job 或 skill 的引用中正确
4. 清理临时文件（克隆的仓库、下载缓存）

**验证**：
```
read_file("SKILL_REGISTRY.yaml") → 确认关联更新
交互验证：新 skill 引用的路径/文件都存在
```

---

### Step 5: 测试 → 跑通核心路径（必须展示实际输出）

**输入**：集成后的产出
**工具**：`terminal` + `execute_code` + `read_file`
**产出**：`research/external/<slug>/test-report.md`

**操作**：
1. 核心路径测试（必须跑通，必须展示**实际终端输出**，不能只说"应该可以"）：
   - 新创建的 skill → `skill_view(name="<新skill>")` 确认加载正常
   - 新写的脚本 → `terminal("python3 <script>")` 确认 exit_code == 0 且输出符合预期
   - 更新的 skill → `skill_view()` 回读确认变更生效
   - cron job → `cronjob(action='run', job_id="...")` 手动执行一次
   - **输出必须通过 read_file/terminal 实际展示给用户**，仅说"通过了"是不够的
2. 边缘测试（可接受降级）：
   - 空输入/异常输入时行为是否优雅
   - 大输入时是否超时
3. 阻塞报告：如果 Ollama 不可用、terminal 超时等环境问题 → **如实报告**，不假装正常
4. 回滚准备：如果测试失败，记录失败点
5. 写入 test-report.md（包含实际命令输出截取）

**验证**：
```
terminal("python3 <new_script>") → exit_code == 0
skill_view("<new_skill>") → 完整加载
cronjob run → exit ok
```

---

### Step 6: 固化 + 汇报

**输入**：所有产出
**工具**：`write_file` + `memory` + `fact_store`
**产出**：总结报告 + 记忆更新

**操作**：
1. 总结本次适配结果给用户：
   ```
   📦 外部来源: <source>
   🔨 拆解: <功能数> 个功能, <文件数> 个文件
   🗺 映射: <映射数> 个外部→内部模式
   🏗 重组: <skill数> / <脚本数> / <引用数>
   ✅ 测试: <通过/失败>
   ```
2. 如果产生新的技能 → 通知用户
3. 将关键发现写入 fact_store（外部项目的设计决策、教训等）
4. 如果本次适配产生重要模式 → memory 写入摘要

**验证**：用户确认："好"/"可以" → 完成。如果用户提出修改 → 回 Step 2。

---

## 4. 工具/Skill 联动表

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill | 触发条件 |
|------|-----------|-----------|-----------|-------------|---------|
| Step 0 | `read_file` + `terminal` + `secure-download` | 外部来源 | `research/external/<slug>/` + `trusted.json` | `secure-download` | 用户提供来源 → 门卫强制校验 |
| Step 1 | `read_file` + `search_files` + `execute_code` | 源文件 | `disassembly.md` | — | 源文件已获取 |
| Step 2 | `skills_list` + `skill_view` + `read_file` | `disassembly.md` + 已有 skill | `mapping.md` | `skill-creation-rules`（格式标准） | 拆解完成 |
| Step 3 | `write_file` + `patch` + `skill_manage` | `mapping.md` | skill 文件 / 脚本 / references | `skill-creation-rules` + `memory-compactor` | 映射完成 |
| Step 4 | `read_file` + `patch` | SKILL_REGISTRY.yaml | SKILL_REGISTRY.yaml + skill 关联字段 | — | 重组完成 |
| Step 5 | `terminal` + `execute_code` + `skill_view` | 新产出文件 | `test-report.md` | — | 集成完成 |
| Step 6 | `write_file` + `memory` + `fact_store` | 所有产出 | 总结 + 记忆 | `memory-compactor` | 测试完成 |

---

## 5. 反馈回路

### 5.1 每步文件验证
每个 `write_file` 后必须立即 `read_file` 回读 → 内容完整才能进下一步

### 5.2 决策可逆
- 失败/回滚路径：如果 Step 5 测试失败
  - 记录失败根因
  - 如果只是小 bug → `patch` 修复后重测
  - 如果映射错误（Step 2 错了）→ 回 Step 2 重做映射
  - 如果设计不兼容 → 标记为"实验性"，通知用户，不集成

### 5.3 迭代上下文
每次适配完成写 `research/external/<slug>/state.json`：
```json
{
  "source": "<url>",
  "status": "done|partial|failed",
  "mapped_patterns": [{"external": "...", "internal": "...", "status": "done"}],
  "unmapped_patterns": [{"pattern": "...", "reason": "不兼容", "notes": "..."}],
  "lessons": ["外部项目XX模式值得关注：..."],
  "context_for_next": "下次 if 网络通了，可以看 XX 项目的 YY 模块"
}
```

### 5.4 合并/去重标记
如果外部内容与已有 skill 合并 → 旧 skill 标记 `status: merged:<target>` 在 SKILL_REGISTRY.yaml 中

### 5.5 长期跟踪
- 对"待网络"的 pending 项目 → 下次网络恢复时提醒用户
- 对"实验性"集成 → 5 天后问用户要不要最终确定

---

## 附录 A：功能拆解（Functional Decomp）

*从 `functional-decomp` skill 吸收*

### 核心目标

提取外部项目做了**哪些事**，产生功能清单。不分析"怎么做到的"，只分析"做了什么"。

### 两种工作模式

**artifact 模式**（外部代码/项目文件可用）→ 以下步骤：
1. 遍历源文件：`search_files(path="<project_dir>", pattern="*.py", target="files")`（或其他语言后缀）
2. 读取入口文件（`main.py`, `app.py`, `cli.py`, `__init__.py` 等）
3. 提取函数/类签名 → `def` / `class` / `async def`
4. 功能归组：导出函数 → 核心 → 工具 → 配置
5. 写 functions.md

**conversation 模式**（用户口头描述，无文件）→ 问 3 个问题：
- 这个项目/工具处理什么类型的输入？（音频？文本？数据？）
- 它产出什么？（转录？报告？配置？）
- 整个过程分成几步？

### 产出格式 `functions.md`

```markdown
# 功能清单：<项目名>

## 核心功能
| 功能 | 入口 | 输入 | 输出 |
|------|------|------|------|
| 转录音频 | `transcribe()` | audio.wav | text |
| 分析情感 | `analyze()` | text | {valence, arousal} |

## 工具函数
| 函数 | 用途 | 被谁调用 |
|------|------|---------|
| `load_config()` | 加载 YAML 配置 | 所有核心功能 |

## 配置/数据
- 配置文件路径、环境变量、命令行参数

## 外部依赖
- Python 包：xxx
- 命令行工具：xxx
```

### 验证
- functions.md 非空
- 每个核心功能有明确的输入/输出
- 无"待确定"条目

### ⚠️ 陷阱
**功能架构分析陷阱**：`functional-decomp` + `arch-decomp` 是**互补**而非替代。先跑功能拆解（提炼概念），后跑架构拆解（映射落地）。不要试图在功能拆解阶段做架构决策。

---

## 附录 B：架构拆解（Architecture Decomp）

*从 `arch-decomp` skill 吸收*

### 核心目标

识别外部项目的**架构风格**、**模块关系**、**控制流**，映射到 Hermes 架构的 tool/skill/cron。

### 入口

| 输入模式 | 触发条件 | 步骤 |
|---------|---------|------|
| **管道模式** | 有 functions.md + 源文件 | 完整以下几步骤 |
| **直问模式** | 用户口头描述架构 | 跳到第 3 步（问架构风格问题） |

### 三步拆解

**Step 1: 架构风格分类**

| 风格 | 特征标记 | Hermes 对应 |
|------|---------|-------------|
| **MVC / Controller** | routers/, controllers/, dispatchers/ | `tool` + `cron` |
| **Plugin 模式** | plugins/, extensions/, providers/ | `skill` |
| **事件驱动** | events/, listeners/, handlers/, queues/ | `cron job` + `tool_post hook` |
| **管道链** | Pipeline class, chained calls, middleware | `terminal(script)` chain |
| **无框架/单片** | 一个文件或互相直接 import | 按功能拆解后逐个 tool |

**Step 2: 模块依赖图**

1. 识别文件间 import/require 关系
2. 找核心入口和依赖树根
3. 记录到 arch-map.md

**Step 3: Hermes 映射**

对每个模块/功能，判断如何落入 Hermes：
- `tool` → 单一操作（tool 函数）
- `skill` → 组合流程（SKILL.md）
- `cron` → 定时任务（cron job）
- `no_agent` → 脚本模式

### 产出格式 `arch-map.md`

```markdown
# 架构映射：<项目名>

风格：[MVC / Plugin / Event / Pipeline / 单片]

## 模块依赖
- module_A → module_B, module_C
- module_B → module_D

## Hermes 映射
| 外部模块 | Hermes 对应 | 类型 | 备注 |
|---------|-------------|------|------|
| routers/ | tool_router | tool | 按路由拆为 N 个 tool |
| services/speech.py | speech_to_text | skill | + cron 定时任务 |
```

### ⚠️ 陷阱
- **不要过度分析**：单片简单项目 >500 行 → 30 分钟分析上限
- **不要混淆「架构风格」和「设计模式」**：如果项目用了工厂模式但整体是无框架单片，风格 = 单片

---

## 附录 C：接口拆解（Interface Decomp）

*从 `interface-decomp` skill 吸收*

### 核心目标

提取外部项目的**核心类/函数签名、参数、返回值**，判断如何适配为 Hermes **tool** 或 **skill action**。

### 提取方法论

1. 扫描源文件：搜索 `def ` 和 `class ` 定义
2. 对每个函数/方法，记录：
   - 签名（含参数类型提示）
   - 返回类型
   - 调用该函数的所有调用点（grep -r "func_name"）
3. 复杂度分类：

| 分类 | 标准 | Hermes 映射 |
|------|------|-------------|
| **简单函数** | ≤3 参数，无外部依赖，无 IO | 直接 tool 函数 |
| **中等函数** | 3-5 参数，依赖 1-2 个其他函数 | tool + validators |
| **复杂函数** | >5 参数，IO/DB调用，内部状态 | 拆为 skill（多步 tool chain） |
| **类/模块** | 有内部状态 + 多方法 | skill（方法拆为独立 action） |

4. 参数级别：
   - 基本类型（str/int/bool）→ 直接映射 tool 参数
   - 复杂对象（Dataclass/Config）→ 拆为多个 tool 参数
   - 可选/默认参数 → tool 参数 default=

### 产出格式 `interface.md`

```markdown
# 接口映射：<项目名>

## 函数级别
| 外部函数 | 参数 | 返回 | 复杂度 | Hermes 映射 |
|---------|------|------|--------|-------------|
| transcribe(audio_path, lang) | str, str|dict | 简单 | tool: audio_transcribe |
| analyze_sentiment(text, model_name, enable_vad) | str, str, bool | dict | 中等 | tool: analyze_sentiment |

## 类级别
| 外部类 | 方法数 | 内部状态 | 映射 |
|--------|--------|---------|------|
| AudioProcessor | 5 | model + cache | skill: audio_processor → 5个action |

## 参数映射详情
- transcribe(audio_path, lang) → tool params: audio_path: string, lang: string(default="zh")
```

### 验证
- interface.md 覆盖所有核心功能
- 每个外部接口有明确的 Hermes 映射决策
- 无"待确定"条目

---

## 附录 D：数据流拆解（Dataflow Decomp）

*从 `dataflow-decomp` skill 吸收*

### 核心目标

追踪外部项目的**数据路径**：从输入→处理链→持久化→输出，识别 Hermes 等效的存储方案、状态管理策略、边界副作用。

### 五步追踪

1. **数据入口**：命令行参数？文件输入？API 调用？用户消息？
2. **处理链**：数据经过哪些函数/管道？每一步做什么？
3. **状态/持久化**：内部状态怎么存的？（全局变量？文件？DB？内存？）
4. **数据出口**：最终输出到哪？（STDOUT？文件？API 响应？）
5. **边界副作用**：网络请求？写系统文件？启动子进程？

### 产出格式 `dataflow.md`

```markdown
# 数据流：<项目名>

## 数据路径
[用户输入] → parse_audio() → transcribe() → analyze() → [STDOUT + report.md]

## 状态管理
- AudioProcessor 在内存中持有 model 实例（重启后丢失）
- 配置文件从 ~/.config/xxx.yaml 读取（stdpath）

## Hermes 映射
| 外部存储 | Hermes 等效 | 备注 |
|---------|-------------|------|
| ~/.config/xxx.yaml | skill frontmatter `config` 字段 | 转为 frontmatter |
| model 实例内存 | `warm_model` 或 lazyload | 关注启动延迟 |
| STDOUT | `terminal()` 输出 | 直接捕获 |
| report.md | `write_file()` | 写入 research/ |
```

### 验证
- 数据路径完整（入口→处理→出口不缺环节）
- 每个外部存储有 Hermes 等效方案
- 边界副作用已标记（哪些需要 tool-governance 规则）

---

## 附录 E：合并/去重标记约定

当外部内容与已有 skill 合并时，旧 skill 在 SKILL_REGISTRY.yaml 中标记：
```yaml
- name: old-skill-name
  status: merged:target-skill-name
```

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

