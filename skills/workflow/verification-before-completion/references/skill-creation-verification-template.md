# 技能创建/修改的验证模板

> 适用场景：完成 verification-before-completion 的"技能创建/修改"验证行。
> 来源：2026-07-25 会话，用户纠正"完成任务前没做测试"后的实战模式。

## 标准验证流程

创建或更新了 N 个 skill 后，不宣称完成，运行以下流程：

### 阶段 1：直接加载验证（所有 skill）

对每个创建/更新的 skill：
```
skill_view(name='<技能名>')
```
- 确认可正常加载，无截断
- 确认 SKILL.md 的 5 个节都完整
- 确认 frontmatter 的 triggers/conditions 正确

### 阶段 2：功能验证（可并行的 skill）

对具有独立可执行机制的 skill，立即使用它们：

| 技能 | 怎么用 | 验证什么 |
|------|--------|---------|
| `verify-before-completion` | 对本次的每个 patch 运行 read_file 回读 | 所有 patch 已正确落地 |
| `dispatching-parallel-agents` | 分派 N 个子智能体，每个验证一个 patch | 每个原始任务目标被独立第三方确认 |
| `deep-need-analysis` | 确认子智能体的输出符合"根因调查→方案"链 | 验证逻辑完整 |

### 阶段 3：分发模板（用于 delegate_task）

```python
# 每个验证子智能体的 context 构造
context = f\"\"\"
## 任务
验证 [{skill_name}] 的 [{feature}] 集成是否完整

## 文件
{file_path}

## 需确认的 {N} 项
1. {item_1} 应出现在行号附近
2. {item_2} 应包含关键词
3. {item_3} 格式正确
...

## 输出要求
逐项确认（存在/缺失），给出行号证据。
\"\"\"
```

### 阶段 4：结论汇总

全部子智能体返回后，汇总成表格：

| 验证项 | 状态 | 证据 |
|--------|------|------|
| skill-X 的 feature-A | ✅ | 子智能体返回：全部存在 |
| skill-Y 的 feature-B | ✅ | skill_view 确认完整 |

**只有全部通过才移除 TODO / 回复完成**。
