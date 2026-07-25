---
name: dependency-tracker
description: 依赖追踪 — 功能/模块之间的依赖关系图、修改影响范围分析、A→B 连锁反应预测。每次修改前自动加载，防止"改了A导致B出问题"。
category: workflow
platforms: [linux, windows]
related_skills:
  - project-lifecycle
  - config-unification
  - quality-gates
triggers:
  keywords:
    - 依赖
    - 影响
    - 连累
    - 关联
    - 牵一发动全身
    - 改了这个会不会
    - 依赖关系
    - 影响范围
    - 连锁反应
    - dependency
    - impact analysis
    - side effect
    - cascade
    - 改动影响
    - 牵连
    - 波及
    - 相关模块
    - 修改影响
    - 风险评估
    - A影响B
---

# Dependency Tracker — 依赖追踪 v1

## 核心问题

改了 A，B 出问题了。因为开发时只考虑了 A 的修改，没有意识到 A 被 B 依赖。需要一个系统化的依赖关系图和改动影响分析。

## 依赖类型

### 1. 代码依赖（静态）

```
文件 A import 文件 B
     ↓
文件 B 的 function X 被 A 调用
     ↓
修改 X 的签名 → A 编译器错误
```

### 2. 配置依赖（运行时）

```
config.yaml: timeout 被 gui.py 和 dashboard.py 同时引用
     ↓
修改 timeout 的单位（秒→毫秒）→ 两个文件都要改
```

### 3. 数据依赖（结构）

```
state.db: 表 users 被 5 个模块读写
     ↓
修改 users 表结构 → 5 个模块都要同步更新
```

### 4. 交互依赖（用户行为）

```
页面 A 跳转到页面 B
     ↓
修改路由 → 页面 A 的跳转链接也要改
```

## 影响分析流程

### 修改前检查清单

```
□ 确定要修改的目标（文件/函数/配置/数据）
□ 搜索哪些内容依赖这个目标
   代码: grep -r "target_function" src/
   配置: grep -r "timeout" config/
   数据: 检查 DB schema 引用
□ 评估影响级别:
   影响文件数 1-2 → 低风险
   影响文件数 3-5 → 中风险（需要 cross-check）
   影响文件数 >5 或跨模块 → 高风险（需要冻结其他修改）
□ 记录影响分析结果
```

### 影响分析报告

```yaml
impact_analysis:
  change_target: "gui.py:render_message_list()"
  change_description: "增加消息摘要显示"
  
  affected:
    - file: "gui.html"
      impact: "需要更新模板"
      severity: "中"
    - file: "dashboard.py"
      impact: "无影响（独立模块）"
      severity: "无"
    - file: "state.db schema messages"
      impact: "摘要字段不需要额外存储（从内容生成）"
      severity: "无"
  
  risk_level: "低"
  recommendation: "可以修改，注意同步更新 gui.html"
```

## 适用场景

### 入口条件
- 开始修改任何代码/配置/数据之前
- 发现 bug 怀疑是副作用导致
- 重构或大规模修改前

### 出口条件
- 影响范围已确定
- 风险级别已评估
- 修改建议已记录
- 高风险变更已通知相关方
