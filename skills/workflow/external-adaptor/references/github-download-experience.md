# GitHub 下载实战记录（2026-07-25）

## 场景
下载 AutoGPT（Significant-Gravitas/AutoGPT）到 Hermes 做拆解分析。

## 网络环境
- Docker bridge 模式，`host.docker.internal:18931` 代理不通（端口未映射）
- `NO_PROXY` 默认排除了 `github.com` → 直连也被绕过
- **修复**：`unset HTTPS_PROXY http_proxy https_proxy HTTP_PROXY; export NO_PROXY="*"`
- 直连速度：~700KB/s，大型仓库需要 >60s

## 尝试的方案

| 方案 | 结果 | 时间 | 结论 |
|------|------|------|------|
| `git clone --depth 1` (4726 files) | 克隆成功但 timeout 签出 (60s) | 60s | 大型仓库用 zipball |
| `curl -L zipball` (14.8MB) | 下载到 14.5MB 后 timeout (30s) | 30s | 需要更久超时 |
| `git restore --source=HEAD :/` | 逐目录签出成功 | ~5s/目录 | 分目录签出可行 |
| `git ls-remote` | 快速（<10s） | 10s | 连通性测试最佳选择 |
| `api.github.com/search/...` | 持续超时 (>15s) | >15s | 不可靠 |
| `api.github.com/repos/owner/name` | 稳定 (<8s) | 8s | 单仓库查询可靠 |

## 最佳实践
```bash
# 1. 测连通性
git ls-remote --heads https://github.com/owner/repo.git

# 2. 小仓库 (<500文件) → git clone
git clone --depth 1 https://github.com/owner/repo.git /tmp/target

# 3. 中大型仓库 → zipball 下载
curl -L --max-time 60 -o /tmp/repo.zip \
  "https://github.com/owner/repo/archive/refs/heads/main.zip"
unzip -q /tmp/repo.zip -d /opt/data/incoming/

# 4. 超大仓库 → 只签出核心子目录
git clone --depth 1 --single-branch --no-checkout URL /tmp/target
cd /tmp/target
git checkout HEAD -- path/to/subdir/
```

## download_gate 集成
- 下载后用 `python3 /opt/data/scripts/download_gate.py scan /path --auto-write` 扫描
- 手动信任特定文件：`python3 /opt/data/scripts/download_gate.py trust <file> --source "github:owner/repo"`
- 不支持目录级 trust → 走 scan --auto-write

## 标记
- Path: `/opt/data/incoming/AutoGPT` (1543 .py, 84MB)
- Cron scanner 下次扫描: 2026-07-26
