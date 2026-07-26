# 记忆架构版本历史

## 版本语义
- v0.x — 架构实施迭代
- v1.x — 正式发布

## 版本记录

| 版本 | 日期 | 关键词 | 内容 | 责任人 |
|------|------|--------|------|--------|
| v0.1 | 2026-07-26 | fix-cron-bugs | 修复Codex脚本缩进bug(3个) + 注册cron: dead_loop_detector(6h) + pattern_analyzer(12h) + capacity_monitor(30m) | Hermes |
| v0.0 | 2026-07-26 | baseline | Codex 部署基线：atomic_write + dead_loop_detector + pattern_analyzer + capacity_monitor + memory-sync + L3空目录 | Codex |

### 回退方式
```bash
git checkout memarch-<version>
# 或部分回退特定文件
git checkout memarch-<version> -- scripts/ scripts/memories/
```
