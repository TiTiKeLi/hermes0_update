# 对抗性验证设计——从一次失败中提炼

## 背景

本系统在一次技能集成后，第一次验证使用了"确认员"角色：
```
goal: "验证 xxx 已正确集成"
context: "检查这些内容是否存在：1) TDD 映射表 2) 四阶方法论..."
```
结果：**3 个子智能体全部返回"全部通过"，发现问题为零。**

第二次验证使用了"审计员/反对派"角色：
```
goal: "审计 xxx 的集成质量——找出任何结构问题、断裂、冗余或错误"
context: "角色：结构分析师/审计员/反对派。失败标准：编号断裂、列不匹配、引用矛盾"
```
结果：**发现 10 个真实问题**（3 严重 + 2 重大 + 3 中等 + 2 轻微）。

## 原理

| 验证类型 | 子Agent实际做的 | 发现问题的概率 |
|----------|---------------|--------------|
| **确认员** | 字符串查找：目标文本是否存在 | ≈ 0%（确认偏差） |
| **审计员** | 结构分析：上下文是否连贯 | 中～高 |
| **反对派** | 质疑假设：是否有矛盾或不可操作 | 高 |
| **结构分析师** | 格式/编号/引用一致性检查 | 中 |

## 规则

1. **Never** leak line numbers or expected content into context
2. **Always** assign a specific adversarial role
3. **Always** define failure criteria in the context
4. **Multiple** independent checks on the same target with different roles
5. **Cross-validate** — if subagent A says "passes" and subagent B says "fails", trust B unless proven otherwise

## 典型违例信号

- 子Agent 返回的内容全部是"✅ 存在"、"✅ 正确"、"✅ 完整"且无编号
- 子Agent 的 goal 中包含"验证xxx已正确..."
- context 里给出了目标行号如"line 96 的段落"
