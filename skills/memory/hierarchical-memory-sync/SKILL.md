---
name: hierarchical-memory-sync
description: Hermes自动记忆分层同步系统 — 将fact_store深层记忆自动同步到memory常驻层，含Hot Cache、实体关联、记忆老化
category: memory
related_skills: [memory-compactor, caveman-compress]
triggers:
  keywords:
      - 记忆同步
      - memory sync
      - 分层记忆
      - hot cache
      - fact_store同步
  events:
      - session_start
      - memory_written
---

# Hierarchical Memory Sync — 自动记忆分层同步 v2

## 设计原理

三层记忆架构：
- **L1 Hot Cache** (memory) — 常驻上下文 ~2KB，放最活跃/高信任度的事实
- **L2 fact_store** (SQLite) — 全量事实，按需检索，含实体关联 + HRR向量
- **L3 Session History** (state.db) — 原始会话记录，session_search 检索

v2 新增特性：
- **Hot Cache** — 实体分组摘要，按优先级排序写入memory
- **实体关联** — 每条事实绑定 entity（如 `user:preference`, `project:audio-vector-system`）
- **代数推理** — `fact_store reason` 跨实体推理
- **记忆老化** — 低信任度(trust<0.4)且长期未访问(retrieval_count=0, last_accessed>60d)自动归档
- **会话热点** — 从最近15条用户消息提取关键词，注入memory

## 数据库结构

facts 表含以下关键列：
- `fact_id` — 主键
- `content` — 事实内容
- `category` — `user_pref`, `project`, `tool`, `general`
- `tags` — 逗号分隔的标签
- `entity` — 实体关联键（如 `user:preference`, `skill:deep-need-analysis`）
- `trust_score` — 信任度 0.0~1.0（通过 fact_feedback 训练）
- `retrieval_count` — 检索次数
- `helpful_count` — 用户标记 helpful 次数
- `last_accessed` — 最后访问时间戳
- `archived` — 0=活跃, 1=已归档
- `hrr_vector` — Holistic Holographic Retrieval 向量

## 实体关联命名规范

```
user:preference          — 用户偏好
user:profile             — 用户画像
user:techstack:python    — 技术栈
user:auth:test           — 认证/验证码
system:host              — 宿主机OS信息
system:storage           — 存储路径
system:llm:ollama        — LLM后端
system:llm:model         — 模型
system:interface:wechat  — 交互渠道
system:resilience        — 弹性/容错
system:meta              — 元信息
project:*                — 项目相关
skill:*                  — 技能相关
```

## 代数推理示例

```python
# 双实体交叉推理
fact_store(action='reason', entities=['skill:deep-need-analysis', 'user:preference'])
# 返回同时关联两个实体的事实（HRR向量相关性排序）
```

## 具体操作命令

### 同步脚本（v3 — 冲突修复版）
- **路径**: `/opt/data/scripts/memory-sync.py`
- **核心变更（v3，2026-07-25）**:
  1. **停止无条件写入根 MEMORY.md** — 优先写 `memories/` 子目录，根目录仅当 mtime 无冲突时选择性写入
  2. **id 级去重** — 扫描已有 fact_id 避免重复追加
  3. **mtime 守卫** — 检测根 MEMORY.md 最近是否被 compactor 修改（<10min → 跳过根写入）
  4. **容量守卫** — 不写入超过 80% 容量限制
  5. **段感知** — 追加到 `## FACTS` 段下而非文件末尾
- **核心逻辑**:
  1. 记忆老化 — 低信任度事实自动归档
  2. 会话关键词 — 从 state.db 提取最近热点
  3. Hot Cache — 按实体分组排序，生成压缩memory
  4. 写入 memories/MEMORY.md（始终）+ 根 MEMORY.md（条件性）

### cronjob 维护
```bash
# 查看
hermes cron list

# 手动触发
hermes cron run --job-id <job_id>
# 或
python3 /opt/data/scripts/memory-sync.py
```

## 记忆老化机制

**自动归档条件**（同步时自动执行）：
- trust_score < 0.4
- retrieval_count = 0
- last_accessed 超过 60 天

**手动归档**（在脚本中调用）：
```python
# 在 sync_memory 中已集成
# 也可单独调用:
from memory_sync import manual_archive
manual_archive([fact_id_1, fact_id_2])
```

## 信任度管理

- `fact_feedback(action='helpful', fact_id=N)` — trust_score += 0.05
- `fact_feedback(action='unhelpful', fact_id=N)` — trust_score -= 0.1
- 直接 SQL 更新（用于确凿事实）:
  ```sql
  UPDATE facts SET trust_score = 0.7 WHERE fact_id = N
  ```

## 注意事项

- memory 有 2200 字符限制 → Hot Cache 按实体优先级截断
- 归档不是删除 —— 归档事实仍在 fact_store 中，按需检索
- `reason` 操作依赖 `entity` 列的正确填充
- 避免重复同步 —— 维护 synced_fact_ids 列表

## 与 Memory Compactor 的冲突（v3 已修复）

详见 `references/sync-compactor-conflict.md`。

### history: v2 时期（2026-07-25 前）的冲突链

`memory-sync.py` 写入**两个路径**：
1. `/opt/data/MEMORY.md`（根目录）
2. `/opt/data/memories/MEMORY.md`（memories/ 子目录）

这直接触发了 `memory-compactor` 的 252MB 死亡螺旋：
- sync 每小时追加新事实到根 MEMORY.md → 文件膨胀
- compactor 每5分钟尝试压缩 → 因 ## IDENTITY 锁丢失 + 旧钩子累积 bug → 文件2倍增长
- sync 再追加更多 → compactor 再2倍增长 → 252MB

### v3 压制策略

| 组件 | 频率 | v3 行为 |
|------|------|---------|
| sync | 每小时 | **只写** `memories/` + 条件写根（mtime 守卫 + id 去重 + 容量守卫） |
| compactor | 每5分钟 | 读根 → 超80%则去重+归档 → 写回（前哨安全检查已激活） |

三把锁确保不会重演：
1. **sync 的 mtime 守卫** — 如果 compactor 刚运行完（<10min），sync 跳过根写入
2. **sync 的 id 去重** — 已存在的 fact_id 不再追加
3. **compactor 的前哨安全检查** — 文件 > 10KB 直接中止

## 与 ToolStateRegistry 的关系

`state_registry.py` (`/opt/data/state_registry.py`) 管理运行时工具/技能的状态注册与健康探测。
`memory-sync.py` 管理记忆分层同步。两者独立运行，但：

- `state_registry.py probe` 每30分钟自动探测所有注册项的健康状态
- 当新 skill 通过 `state_registry.py register` 注册时，关联的事实会被自动同步到 fact_store（通过 on_memory_write hook，如果已启用）
- 任何注册项的 trust_score 变化不会自动同步到 state_registry——这是单向的：fact_store

## 引用文件
- `scripts/memory-sync.py` — v2 同步脚本（15.7KB，完整实现）
