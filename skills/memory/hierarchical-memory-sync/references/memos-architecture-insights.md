# MemOS 记忆架构借鉴笔记

> 来源：MemTensor/MemOS (10.4k stars) — 深度学习代理的类脑存储系统  
> 日期：2026-07-25  
> 用途：为 Hermes 记忆系统（memory-compactor + hierarchical-memory-sync + fact_store）提供架构改进方向

---

## 1. MemOS 核心架构（五层记忆层次）

| 层次 | 名称 | 特征 | MemOS 实现 | Hermes 当前状态 |
|------|------|------|-----------|----------------|
| L1 | 工作记忆 | 当前会话上下文，自动清空 | Token 窗口 + 显式上下文网络 | ✅ MEMORY.md + USER.md（常驻） |
| L2 | 短期记忆 | 近 N 小时会话，自动归档 | 时间衰减索引（TTL-based） | 🔶 memories/<date>.md（线性文件，无索引） |
| L3 | 长期记忆 | 持久化知识，需显式回忆 | 嵌入向量索引 + 优先级排序 | 🔶 fact_store（结构化，但无嵌入） |
| L4 | 语义记忆 | 抽象概念，跨会话模式 | 概念图谱 + 推理链路缓存 | ❌ 无 |
| L5 | 程序记忆 | 技能/过程性知识 | 独立模块，可加载/卸载 | ✅ skills/ 体系（有，但无版本/演化追踪） |

**差距分析：**
- L2 无 TTL/时间衰减索引 → 归档文件是线性追加，检索需要全文扫描
- L3 无嵌入向量 → 语义搜索依赖 keyword match (FTS5)
- L4 缺失 → 无法跨 session 发现概念关联和推理模式
- L5 无版本/演化追踪 → skill 迭代没有变更历史

---

## 2. 可借鉴的关键模式

### 2.1 记忆优先级索引（Memory Priority Indexing）

**MemOS 做法：**
每条记忆带 `priority_score` (0-1.0)，检索时按 priority × recency 排序返回 top-K。高优先级记忆在上下文中保留更长时间。

**Hermes 应用建议：**
- fact_store 已有 trust_score（信任度），但未和 recency 组合
- 在记忆同步脚本（memory-sync.py）中加入：
  - 同步时计算 `composite_score = trust_score × 0.7 + recency_norm × 0.3`
  - 高 composite_score 的事实优先写入 MEMORY.md
  - 低分事实延迟写入或跳过

### 2.2 上下文感知召回（Context-Aware Recall）

**MemOS 做法：**
根据当前 session 的主题标签（topic tags）过滤记忆召回范围。例如 topic=debugging 时只召回调试相关记忆。

**Hermes 应用建议：**
- MEMORY.md 当前是全量注入→对大 context 模型友好但对 3B 模型浪费
- 改为分层注入：只有 topic 相关的事实进入 header
- 实现方式：在记忆同步任务（cron）中根据 session 前 N 轮的关键词检测 topic

### 2.3 记忆衰减与强化（Memory Decay & Consolidation）

**MemOS 做法：**
- 未访问的记忆每 tick 衰减 0.01 priority
- 被成功召回的 +0.05
- 低于 threshold 的记忆自动归档到冷存储（L4→L5 降级）

**Hermes 应用建议：**
- fact_feedback 已有 helpful/unhelpful 机制，但无自动衰减
- 在 cron 任务中加入月级衰减：30 天未使用的 fact → trust_score -= 0.1
- 连续 3 个 unhelpful → 标记 `stale`（但保留为参考）

### 2.4 冲突检测（Contradiction Detection）

**MemOS 做法：**
每个 L3 记忆有 `contradicts: [id1, id2]` 字段。写入新记忆时与同 entity 的已有记忆对比语义相似度+矛盾度。

**Hermes 应用建议：**
- fact_store 已有 `contradict` action（但无自动触发）
- 在 memory-sync.py 中加入写入前矛盾检查：查询同 category 的已有事实，若矛盾则触发 human-in-loop 标记
- 暂不自动解决，仅标记 `contradicts: fact_id` 供手动 review

### 2.5 情感标记（Affective Tagging）

**MemOS 做法：**
记忆附带情感维度（positive/negative/neutral），影响 recall 优先级。
例如：负面调试经验比中性事实更可能在类似场景被召回。

**Hermes 应用建议：**
- fact_store 可增加 `affect` 标签（痛苦/失败/成功/中性）
- 在代理遇到类似错误时优先召回带 `失败` 标签的事实
- 实现：最简单方案是在 category 上加 subcategory（`project:pain_point`）

---

## 3. Hermes 记忆系统改进路线图

### P0（立即受益，低工作量）

1. **记忆同步脚本加分值排序** — 修改 `memory-sync.py`，用 trust_score × recency 组合排序事实，高分优先写入 MEMORY.md
2. **记忆衰减 cron** — 每月一次，扫描 fact_store 中 30 天未使用的 fact，trust_score -= 0.1

### P1（中等收益，中等工作量）

3. **topic 感知筛选** — 在同步脚本中检测 session 主题，只写入相关事实
4. **冲突自动标记** — 写入 fact_store 前检查 category 内矛盾事实

### P2（高收益，高工作量）

5. **嵌入向量存/检索** — 为 fact_store 增加 embedding 字段，用 cosine sim 替代 keyword 检索
6. **L4 概念图谱** — 跨 session 提取重复出现的实体/模式，构建推理链路
7. **情感标记** — 增加 affect 字段，在事实写入时向 LLM 问一句情感标签

---

## 4. 对现有系统的直接影响

### memory-compactor 相关
- 压缩时保留 priority_score 高的条目，而不仅是按 section 保留最后 N 条
- 归档时记录原 priority_score，供恢复时参考

### memory-sync 相关
- 同步顺序：composite_score 从高到低
- 写入 MEMORY.md 时不超过 65% 容量阈值（约 1,430 chars / 2,200）

### fact_store 相关（已在现有 hooks 中注册）
- hooks ID: FS_MEMOSYNC → fact_write 后自动同步
- 考虑增加：fact_write 前调用 `contradict` 检查一次

---

## 5. 不采纳的设计（有明确拒绝理由）

| MemOS 功能 | 理由 |
|-----------|------|
| L1 工作记忆自动清空 | Hermes 的 MEMORY.md/USER.md 是持久注入，非会话级 |
| 全量嵌入向量索引 | 需要外部向量数据库+embedding 模型（Ollama 不可达时断线） |
| 情感维度全自动标注 | 增加事实写入时延 + API 调用，价值/成本比存疑 |
| L5 程序记忆版本图谱 | Hermes skill 体系已有 skill_manage 版本控制，不需额外层 |
