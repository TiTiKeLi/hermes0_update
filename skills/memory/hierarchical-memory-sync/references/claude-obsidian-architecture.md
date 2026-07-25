# Claude-Obsidian 架构深度分析（参考文档）

> 来源: https://github.com/AgriciDaniel/claude-obsidian
> 下载于: 2026-07-21

## 核心哲学

**"The wiki is the product. Chat is just the interface."**

与RAG的关键区别：Wiki 是持久化产物，交叉引用已存在，矛盾已被标记，知识像复利一样累积。

## 架构层次

### 三层存储

```
vault/
├── .raw/              # L1: 不可变的原始源文档
├── wiki/              # L2: LLM 生成的知识库
│   ├── sources/       #   源文档摘要
│   ├── entities/      #   人物/组织/产品
│   ├── concepts/      #   概念/框架
│   ├── sessions/      #   会话记录
│   └── folds/         #   知识折叠结果
├── CLAUDE.md          # L3: Schema + 指令
└── .vault-meta/       #    元数据（地址、锁、模式配置）
```

### 记忆分层架构

| 层 | 文件 | 大小 | 更新时机 | Hermes等价 |
|---|---|---|---|---|
| **L0 热缓存** | `wiki/hot.md` | ~500字 | 每次ingest后、会话结束时 | `memory` (2KB) |
| **L1 索引** | `wiki/index.md` | ~1000字 | 每次页面创建/更新后 | `fact_store` |
| **L2 语义检索** | `.vault-meta/chunks/` + BM25 | chunk级别 | 首次setup + 按需重建 | `session_search` |
| **L3 全息折叠** | `wiki/folds/` | 折叠摘要 | 日志达到2^k时 | 可类比DragonScale |

## 核心机制

### 1. Hot Cache (hot.md)
- 每次session启动时自动加载到上下文
- 每次session结束时自动更新
- 一问一答：**"where did we leave off?"**
- 500字限制，完全覆盖，不是追加
- 格式：Last Updated / Key Recent Facts / Recent Changes / Active Threads

### 2. Compounding Knowledge（复利知识）
- 每输入一个源，不建立索引，而是**集成**：
  - 更新实体页面
  - 标记矛盾
  - 加强/挑战现有共识
  - 添加交叉引用
- 每次查询也回馈新的wiki页面

### 3. DragonScale Memory（龙鳞记忆）
四个机制，四个层次：

**M1 — 折叠操作符**：日志达到2^k条时，生成摘要折叠页。折叠是**累加的**（子页面永远保留），类似物化视图而非LSM压缩。

**M2 — 确定性地址**：每个新页面有 `address: c-000042` 唯一ID。计数器由 `scripts/allocate-address.sh` 管理。

**M3 — 语义平铺检查**：embedding去重（nomic-embed-text本地运行）。相似度≥0.9标记为近重复。**不自动合并**，输出人工审查列表。

**M4 — 边界优先自动研究**：出度>入度的页面是"边界"（信息输出点），推荐给用户作为下一步研究方向。议程控制而非纯记忆。

### 4. 多Agent协作模式

```
agents/
├── wiki-ingest.md    — 并行批量摄入
├── wiki-lint.md      — Wiki健康检查
└── verifier.md       — 预提交代码审查
```

每个agent有自己的model、maxTurns、tools配置。通过 delegate_task 并行分发。

### 5. 事件钩子系统（hooks.json）

```
SessionStart  → 自动加载 hot.md
PostCompact   → 上下文压缩后重新加载 hot.md
PostToolUse   → 自动 git commit 任何wiki改动
Stop          → 更新 hot.md（如果wiki有改动）
```

## 对 Hermes 的适配建议

1. **Hot Cache 模式**：memory 已类似 hot.md，但缺**自动清空和覆盖**机制。建议 cronjob 每轮对话后更新一个固定摘要。
2. **复利集成**：fact_store 存储事实但缺乏 "标记矛盾" 和 "强化共识" 的能力。可以考虑添加 contradiction 字段。
3. **折叠机制**：当 fact_store 事实数超过阈值（如50条）时，生成折叠摘要存入 memory。
4. **边界引导**：利用 fact_store 的 trust_score 作为"边界"评分，高 trust 但低使用率的事实推送给用户主动确认。
5. **参考 _templates/**：可以为 AudioVectorSystem 设计结构化模板（音频源、转录、分析结果、对比）。

## 注意事项

- DragonScale 强调**累加而非压缩**：子页面永远保留，折叠是物化视图
- 所有操作是**幂等的**：重新执行产生相同结果
- **没有自动删除**：页面是永久的，除非人工干预
- **单写者假设**：一次只有一个Agent写操作（Hermes也是单会话）
