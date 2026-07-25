# Agent 记忆体系详细对比表

## 全景对比

| 维度 | MemGPT/Letta | Mem0 | Zep | LangGraph | GraphRAG | **Hermes 当前** |
|------|-------------|------|-----|-----------|---------|-----------------|
| **架构风格** | 双块 Core + Archival | 向量嵌入 + 图存储 | 独立服务 + 实体图 | Checkpoint + State | 知识图谱 RAG | flat MEMORY.md + fact_store |
| **Core Memory** | Persona+Human JSON | 无显式 Core | 无显式 Core | State 任意结构 | 无 | flat IDENTITY + FACTS |
| **去重方式** | 无（Core 独占） | embedding 语义相似度 | 无（追加模式） | 无（state update = overwrite） | 图节点去重 | id:N 精确匹配 |
| **记忆提取** | 系统级自动 | 对话流自动 parse | 对话流自动 parse | 显式 state mutation | 文档解析 | agent 手动调用 memory tool |
| **上下文注入** | 全 Core + 语义检索 | 语义检索 TOP-K | 实体相关检索 | 全部 state | 社区摘要 | 固定 2200 字符 |
| **摘要机制** | 自动摘要链 | 事实压缩 | 多层次时间摘要 | 无 | 社区分层摘要 | 无（硬归档） |
| **关系维度** | 无（独立事实） | 元数据标签 | Entity Graph | 无 | 社区检测 | fact_store reason（近似） |
| **本地模型友好** | ❌ 需强模型 | ❌ 需 embedding API | ❌ 外部服务 | ✅ 轻量 | ❌ 需 LLM | ✅ 纯 Python + 3B |
| **依赖** | 大模型 + 向量 DB | API key | Zep 服务 | ❌ 无 | LLM + 向量 DB | 零依赖 |
| **实现复杂度** | 高 | 中 | 中（部署服务） | 中 | 极高 | 低 |

## Hermes 适配可行性矩阵

| 模式 | 业界参考 | 本地 3B 可行？ | 实现路径 |
|------|---------|---------------|---------|
| Core Memory 双块 | MemGPT | ✅ 纯结构变更 | MEMORY.md 改三段：IDENTITY(Persona)/HUMAN(User)/FACTS |
| 自动事实提取 | Mem0 | ✅ 3B 够做模式匹配 | POST_REPLY hook 触发 parse 脚本 |
| 语义去重 | Mem0 | ❌ 无 embedding | 退化：关键词 + tag + 实体三元组 |
| 语义检索注入 | Mem0/MemGPT | ❌ 无 embedding | 退化：fact_store search + 关键词匹配 |
| Entity Graph | Zep | ✅ 纯 SQLite 关系表 | fact_store 加 relation 表 + entity 外键 |
| 多层次摘要 | Zep | ⚠️ 需 3B 摘要 | cron 触发 summary.py（依赖 Ollama） |
| Hook↔Memory | LangGraph | ✅ 轻量 | hooks_engine 加 memory_update action 类型 |
| 社区检测 | GraphRAG | ❌ 需强 LLM | 不可行 |
| 前哨安全检查 | — | ✅ 已有 | memory_compactor_v2.py 行数/大小守卫 |

## 优先级建议

### P0（立即，1-2 次会话）
1. **Hook↔Memory 联动** — hooks_engine 加 memory_update action，现有钩子+记忆打通
2. **自动记忆萃取** — POST_REPLY 钩子触发 parse 脚本，被动从回复中提取事实

### P1（本周，2-4 次会话）
3. **Core Memory 结构化** — MEMORY.md 改 Persona/Human 双块
4. **fact_store 关系表** — entity 外键 + relation 表，升级到实体图

### P2（本月）
5. **语义检索退化实现** — 关键词 + tag + entity 综合检索注入
6. **多层次摘要 cron** — 调用 3B 生成归档摘要

### P3（长期）
7. **3B 模型能力提升后评估** — 如果升级到 7B 以上，考虑 embedding + 语义检索
