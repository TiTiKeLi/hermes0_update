# Codex 前导空格 Bug 模式（2026-07-26 发现）

## 现象

Codex 写回的 Python 脚本多个文件在第1行有前导空格，导致 Python 报 IndentationError。

## 受影响文件（2026-07-26）

- `scripts/dead_loop_detector.py` — 第1行 ` #!/usr/bin/env python3`
- `scripts/pattern_analyzer.py` — 同上
- `scripts/capacity_monitor.py` — 同上

未受影响: `scripts/atomic_write.py` — 正常

## 根因

Codex 一次写多文件时，部分文件的 shebang 行被加上前导空格。模式是第1行 header/import 区整块缩进，函数定义行正常。

## 修复方法

用 patch 工具移除每行的前导空格:
```
patch --path scripts/xxx.py \
  --old_string " #!/usr/bin/env python3" \
  --new_string "#!/usr/bin/env python3"
```
然后逐行检查后续行（import、常量定义）是否也有前导空格。

## 预防

在 Step 5（验证）中必须增加: `python3 script.py` 运行测试。
只看文件存在和代码内容无法发现此问题——这是运行时才暴露的 bug。
