---
name: github-discover
description: 深度研究型 GitHub + arXiv 开源项目发现、评估、提取、部署管道。当用户需求需要外部依据时，按本协议搜索→提取→吸收→落地，形成可迭代的知识闭环。
category: workflow
conditions:
  requires_toolsets:
    - terminal
    - file
    - web
platforms: [linux]
related_skills: [hermes-optimization, memory-compactor]
triggers:
  keywords:
    - GitHub
    - 开源项目
    - 发现项目
    - 搜索项目
    - GitHub搜索
    - github discover
    - find repo
    - 开源发现
    - 项目发现
    - GitHub项目
    - repo搜索
  events:
      - user_request
---

# GitHub Discover v3 — 可执行协议

## 1. 边界条件

### 入口条件

- 用户需求需要外部 GitHub 项目支持
 - 当前本地项目无法满足需求
 - 需要寻找开源解决方案

### 跳过条件（任何一条满足就直接跳过，不走任何研究步骤）
- [ ] 用户需求仅需本地知识就能回答（已有 skill / 已有 fact_store 记录）
- [ ] 用户在明确说"不要联网""不要搜外部""自己搞"
- [ ] 连续 3 次同主题研究后，结果均为"无可用的开源项目或论文"
- [ ] 容器无外网且用户已明确说"不要再试网络了"

### 中止条件（执行中，任何一条满足立刻终止）
- [ ] 用户插入新消息切换了话题
- [ ] 网络原本可用 → 执行到一半断联
- [ ] 连续搜索 2 轮返回空结果（说明搜索词有问题或该领域没有开源成果）
- [ ] 单步执行超时（terminal timeout > 30s | execute_code > 60s）

---

## 2. 决策矩阵

| # | 场景 | 行动 | 工具链 | 产出位置 |
|---|------|------|--------|----------|
| 0 | 需求未拆解 | Step 0：追问用户确认本质需求 | `clarify` | fact_store |
| 1 | 需求已确认+网络通 | Step 1→2→3→4→5 全链路 | `terminal`/`execute_code` + scripts | `research/topics/<slug>/` |
| 2 | 需求已确认+网络不通 | Step 1 节流：记录排队，告知用户 | `write_file` | `research/topics/<slug>/pending.txt` |
| 3 | 网络半通（terminal不通但execute_code通） | 降级用 `execute_code` + `urllib` | `execute_code` | `research/sources/` |
| 4 | 搜索连续空结果 | 中止，告知用户"该方向暂无开源依据" | — | — |
| 5 | 发现与已有 skill 重叠 | 不新建，更新已有 skill | `skill_manage action=patch` | skill 文件 |
| 6 | 发现需要新 skill | 问用户确认后再创建 | `clarify` + `skill_manage action=create` | skill 目录 |
| 7 | 发现可部署到 Hermes | 写文件+注册+验证 | `write_file`+`terminal`+`read_file` | `state_registry`+references |
| 8 | 执行结果需要保存供下次 | Step 5：写迭代上下文 | `write_file`+`memory` | `research/topics/<slug>/state.json` |

---

## 3. 步骤协议（可执行）

### Step 0：需求拆解 → 本质锚点

**输入**：用户的原始需求文字
**工具**：`clarify`
**产出**：一个本质锚点（存到 fact_store）

```
操作：
  1. 问自己："用户真正的目标是什么？不是他说的表面，是最终要什么效果？"
  2. 若不确定 → call `clarify(question="你说的X，是指Y还是Z？确定后再搜")`
  3. 若确定 → 写本质锚点：
     fact_store_add(
       content="需求锚点: <用户一句话本质目标>",
       entity="research:anchor",
       tags="anchor"
     )
  4. 若用户无法确认 → 取最宽泛的理解，作为 anchor_tag="fuzzy"
```

**验证**：用户回了确认或我没法再追问了
**跳过条件**：用户需求极其明确（如"研究 langchain tool registry"）

---

### Step 1：搜索 → 验证锚点一致性

**输入**：本质锚点
**工具链**：
- 网络通 + web_search 可用：`terminal("python3 /opt/data/scripts/search_github.py '<query>' 5")` 或 `execute_code()`
- 网络通 + 仅有 terminal（无 web_search 工具）：**方法 B — 直接 HTTP scraping**（见参考文件 `references/github-scraping-without-web-tools.md`）
- 网络通 + 无 Python 无 web_search：**方法 C — grep 轻量提取**（同样见参考文件）
- 网络不通：`write_file(path="research/topics/<slug>/pending.txt", content="需求+时间")`
- 关联 skill：`hermes-optimization`（网络诊断部分）
**产出**：`research/sources/github-<slug>-<ts>.json` 或 `research/sources/github-<slug>-<ts>.txt`（方法 B/C）

```
操作：
  1. 从本质锚点拆 3-5 个搜索词
  2. 每个搜索词分别搜 GitHub + 其他来源（arXiv 可走同一 scraping 方案）
  3. 结果去重
  4. 验证：结果是否与本质锚点对齐？
     - 如果结果跑偏 → 回 Step 0 重新拆解
     - 如果结果合理 → 进入 Step 2
  5. 如果全部为空 → 中止
```

**文件验证**（方法 A）：
```
read_file(path="research/sources/github-<slug>-<ts>.json")
→ 确认有 items 且 > 0
→ 确认每个 item 有 name, stars, description
```

**文件验证**（方法 B/C）：
```
read_file(path="research/sources/github-<slug>-<ts>.txt")
→ 确认有项目名列表
→ 每个项目都有星级标注
```

---

### Step 2：筛选 → 最多 3 个项目

**输入**：搜索结果 JSON
**工具**：`read_file` + `execute_code`（处理JSON）
**产出**：筛选列表写入 `research/topics/<slug>/selected.md`

```
操作：
  1. 按优先级排序：
     - stars > 1000 且最近 3 个月有提交
     - 许可 MIT / Apache 2.0 / BSD
     - 与本质锚点直接相关（不是边缘相关）
  2. 选 top 3，写入筛选表：
     | # | 项目 | ⭐ | 许可 | 最后更新 |
     |---|------|----|------|----------|
  3. 跳过的项目记到 selected.md 的"已排除"节，注明原因
```

**文件验证**：
```
read_file(path="research/topics/<slug>/selected.md")
→ 确认含 1-3 个选中的 + 跳过的 + 原因
```

---

### Step 3：深度提取 → 五维分析

**输入**：selected.md
**工具**：`execute_code`（urllib.fetch 单文件）+ `read_file`
**产出**：`research/topics/<slug>/analysis.json`（结构化）

```
操作为每个选中的项目独立执行：
  1. 入口提取：fetch README.md + 核心文件列表
  2. 五维分析：
     维度A - 架构骨架（入口→模块→依赖图）
     维度B - 核心接口（类/函数签名 + 参数 + 返回值）
     维度C - 数据流（输入→处理→输出 的完整路径）
     维度D - 设计选择（为什么这样不是那样 + 替代方案）
     维度E - 已知教训（Issues/PRs 里的坑）
  3. 写入 analysis.json
     {
       "project": "owner/repo",
       "stars": N,
       "architecture": { "summary": "...", "modules": [...] },
       "interfaces": [{ "name": "...", "signature": "...", "purpose": "..." }],
       "dataflow": "输入→...→输出",
       "choices": [{ "what": "class-based", "why": "生命周期管理", "alt": "function-based", "why_no": "无状态" }],
       "lessons": [{ "issue": "并发锁竞争", "fix": "RLock 保护" }]
     }
```

**验证**：
```
read_file(path="research/topics/<slug>/analysis.json")
→ 每个维度都有内容，不为空
→ 设计选择至少 2 个（证明不是表面阅读）
→ 如果 lessons 为空 → 回去看 Issues 前 10 条再补
```

---

### Step 4：吸收 → 映射 + 适配 + 落地

**输入**：analysis.json
**工具**：`read_file` + `skill_manage` + `write_file` + `patch`
**产出**：落地清单 `research/topics/<slug>/deploy.md`

```
操作：
  1. 对每个发现模式，做 delta 分析（原项目的假设 vs Hermes 的实际）：
     ```
     模式: Registry Pattern
     原项目假设:
       - 单进程同步调用
       - 工具是子进程启动
      Hermes 实际:
       - 多线程可能
       - 工具是 Python 函数
      delta: 需要加 Lock，不需要进程管理
     ```
  2. 决策树：
     模式 deps 都满足 → 直接引用（更新 skill references/）
     模式需要小改 → 写实现 + 注册（write_file + state_registry）
     模式需要大改 → 写分析笔记到 references/，下次迭代实现
  3. 写入 deploy.md
```

**文件验证**：
```
read_file(path="research/topics/<slug>/deploy.md")
→ delta 分析不为空
→ 每个模式的决策结果明确（引用/实现/笔记）
→ 如果选了"实现" → 确认文件已经 write_file 成功
→ 回读确认 write_file 的内容完整：read_file(path=刚写的文件)
```

---

### Step 5：知识固化 + 迭代上下文

**输入**：本轮所有产出
**工具**：`write_file` + `memory` + `fact_store`
**产出**：`research/topics/<slug>/state.json` 更新 + fact_store 记录

```
操作：
  1. 更新 state.json：
     {
       "topic": "...",
       "anchor": "本质锚点",
       "last_run": "2026-07-24T12:00:00",
       "iterations": [
         {
           "num": 1,
           "what_searched": ["查询词1", "查询词2"],
           "what_found": { "projects": N, "papers": N },
           "what_absorbed": ["模式1→deploy.md", "模式2→references/"],
           "what_remaining": ["delta分析中判定'下次实现'的部分"]
         }
       ],
       "context_for_next": "下次时，从 remaining 开始，搜索词可以加上: ..."
     }
  2. 如果本轮有可消化的知识点 → memory 写入摘要
  3. 如果本轮有新的实体/概念 → fact_store 记录
```

**验证**：
```
read_file(path="research/topics/<slug>/state.json")
→ 有 context_for_next（证明下次能接着干）
→ iterations[-1].what_remaining 有内容（如果没有，说明全部吃透了）
```

---

## 4. 工具/skill 联动表

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill | 触发条件 |
|------|-----------|-----------|-----------|-------------|---------|
| Step 0 | `clarify` + `fact_store` | — | fact_store | — | 需求语义模糊 |
| Step 1 | `terminal`/`execute_code` | — | `research/sources/*.json` | `hermes-optimization`（网络诊断） | 网络状态未知 |
| Step 2 | `read_file` + `execute_code` | sources JSON | `selected.md` | — | sources 非空 |
| Step 3 | `execute_code` + `read_file` | 远程文件 | `analysis.json` | — | selected 非空 |
| Step 4 | `read_file` + `write_file` + `patch` + `skill_manage` | analysis.json | `deploy.md`, 实际代码/配置 | `memory-compactor`（压缩 memory） | analysis 完成 |
| Step 5 | `write_file` + `memory` + `fact_store` | state.json | state.json | `memory-compactor` | deploy 完成 |

---

## 5. 反馈回路（防止空转）

### 5.1 文件写入后验证
write_file 之后 → 必须马上 read_file 回读 → 内容完整才继续

### 5.2 回复固化
每次执行完本协议后，最终回复的内容必须固化：
```
write_file(
  path="research/topics/<slug>/reply-<ts>.md",
  content="<我最终回复用户的完整内容>"
)
```

### 5.3 下一次迭代的入口
下次对同一话题的请求进来：
```
1. 读 research/topics/<slug>/state.json → 看 context_for_next
2. 看上次的 what_remaining 有什么
3. 从 Step 0 开始，但搜索词追加 context_for_next 的关键词
```

### 5.4 三次空结果自动降级
```
if 连续 3 次搜索空结果:
  write_file(path="research/topics/<slug>/DEADEND", content="原因+时间")
  → 该话题标记为"无开源依据"，下次直接跳过搜索
```

### 出口条件

- 问题已解决或结论已输出
- 所有必要的操作已完成
- 结果已向用户报告

