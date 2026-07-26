---
name: chinese-format
description: 中文格式强制 — 所有输出必须使用中文，禁止英文状态消息
category: behavior
platforms: [linux, windows]
related_skills:
  - wechat-format
  - caveman
  - chinese-output
triggers:
  keywords:
    - 中文
    - 语言
    - 英文
    - 翻译
    - 说中文
    - 不要英文
    - 中文回复
    - language
    - chinese
    - 用中文
    - 请说中文
    - 强制中文
---

# 中文格式强制 v1

## 核心规则

所有输出必须使用中文。禁止出现以下情况：

```
❌ "created: sm-xxx"
❌ "running: ok"
❌ "status: completed"
❌ "cleaned 0 tmp files"
❌ 任何英文状态消息
```

必须转换为：

```
✅ "已创建: sm-xxx"
✅ "状态: 已完成"
✅ "已清理 0 个临时文件"
✅ "正在运行"
```

## 强制范围

| 场景 | 英文（禁止） | 中文（强制） |
|------|------------|------------|
| 状态消息 | "completed", "failed" | "已完成", "失败" |
| 操作动词 | "created", "cleaned" | "已创建", "已清理" |
| 确认提示 | "confirm?", "approve?" | "确认执行？", "是否批准？" |
| 错误提示 | "error:", "failed:" | "错误:", "失败:" |
| 工具输出 | Python print 输出 | 所有 print 必须是中文 |
| 状态机 | "PENDING", "PROCESSING" | "待处理", "处理中" |
