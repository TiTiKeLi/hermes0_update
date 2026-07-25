---
name: memory-confirmation-feedback
description: 记忆写入后反馈新事实与已有记忆的关联网络，一行一条，一瞥即知。绑定 memory_write_occurred 参数，仅本会话有写入时激活
category: behavior
triggers:
  keywords:
      - 记忆确认
      - memory feedback
      - 记忆反馈
      - feedback protocol
      - memory_write_occurred
  events:
      - memory_written
---

# 记忆确认反馈协议 v4

## 核心原则

1. **不罗列存了什么** — 展示新事实在已有知识网络中的位置
2. **一瞥即知** — 全部压缩到一行，无换行无分段
3. **无写入沉默** — 没有记忆写入的回复不产生任何反馈
4. **语言统一** — 反馈内容使用简体中文，仅代码/专有名词保留英文
5. **写入后必须触发** — 每次 memory action=add/replace 后，下一条回复末尾必须附关联反馈，不得遗漏

## 激活机制

```
memory_write_occurred: false
```

写入操作后 → true → 回复末尾附关联反馈
反馈完成后 → false（下一轮重置）

## 反馈格式（一行版）

```
✅ id:N [tag] 摘要 ~ id:M [tag] 摘要 (理由)
```

**规则**：
- 全部在**一行内**，多条事实用 ` · ` 分隔
- `[tag]` 取 entity 最后一段，控制在 3-6 字
- 摘要 ≤20 字（一瞥内读完）
- 关联指向 1 条已有事实 `id:M`，理由用 2 字标注
- 理由缩写：`同类` `互补` `因果` `同源` `矛盾`

### 单条示例

```
✅ id:21 [confirm] 绑定 memory_write_occurred ~ id:19 [deep-need] 同类
```

### 多条示例

```
✅ id:21 [confirm] 绑定写入参数 ~ id:19 [deep-need] 同类 · id:20 [memory] 反馈固化 ~ id:9 [audio] 同源
```

### 无关联时

```
✅ id:21 [confirm] 绑定写入参数（孤立）
```

## 纠错

```
↩️ id:N [tag] 修正摘要 ~ id:M [tag] 理由
```

## 跨会话保障

- SKILL.md 磁盘持久化，每次新会话自动扫描加载
- `memory_write_occurred` 参数定义在 skill prompt 中，不依赖会话历史
- memory 中存有 fallback 条目（id:20）