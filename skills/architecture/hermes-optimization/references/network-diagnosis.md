# 容器网络诊断 (Network Diagnosis)

## 适用场景

容器内无法访问外网（API 调用失败、`Connection error`、`web_search` 不可用）。

## 分层排查流程

### Layer 1: 基础存活确认

```bash
echo "alive" && date
# 如果这个也超时 → 容器/终端故障，非网络问题
```

### Layer 2: DNS 解析

```bash
# 查看 /etc/hosts 中 host.docker.internal 的解析地址
cat /etc/hosts

# 查看 DNS 配置
cat /etc/resolv.conf
```

**已知模式**：
- Docker Desktop: `host.docker.internal` → `192.168.65.254`（内部网关，不是宿主机真实 IP）
- 外部 DNS: `192.168.65.7`（Docker 内部 DNS 代理）
- DNS 配置在 `/etc/resolv.conf`：`nameserver 127.0.0.11`（Docker 内置 resolver）

### Layer 3: 网络接口与路由

```bash
cat /proc/net/route   # 默认网关
ls /sys/class/net/    # 网络接口列表
```

**解释路由表**（/proc/net/route 的 Gateway 字段是 little-endian hex）：
- `010013AC` → `172.19.0.1`（小端序，`AC`=`172`, `13`=`19`, `00`=`0`, `01`=`1`）

### Layer 4: TCP 出站测试

**重要**：不要用 `ping`（ICMP 可能被 Docker 网络层拦截），也不用 `/dev/tcp`（bash 内置 TCP 在受限容器中会卡死）。用 Python socket：

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(4)
result = s.connect_ex(('host.docker.internal', 18931))
print(f'result={result} (0=OK, 111=refused, 110=timeout)')
s.close()
```

**`connect_ex` 返回码含义**：
- `0` — 连接成功
- `111` — 连接被拒绝（端口未监听）
- `110` — 连接超时（网络层不通或防火墙拦截）
- `101` — 网络不可达

### Layer 5: 环境变量

```bash
echo "HTTP_PROXY=$HTTP_PROXY"
echo "HTTPS_PROXY=$HTTPS_PROXY"
echo "http_proxy=$http_proxy"
echo "https_proxy=$https_proxy"
echo "NO_PROXY=$NO_PROXY"
echo "ALL_PROXY=$ALL_PROXY"
```

**已知陷阱**：Python 的 `requests`/`httpx` 只认小写 `http_proxy`/`https_proxy`，大写版本被忽略。如果容器只设了大写版本，Python 发包会直连而不走代理。

**Hermes 特有**：Docker 环境变量通过 `TERMINAL_DOCKER_ENV` JSON 字符串注入，`env|grep proxy` 可能同时显示大小写版本。

### Layer 6: 关键端口可达性

| 端口 | 用途 | 测试命令 |
|------|------|---------|
| `host.docker.internal:18931` | 代理服务（Host Proxy） | `python3 -c "import socket; s=socket.socket(); s.settimeout(3); r=s.connect_ex(('host.docker.internal',18931)); print('OK' if r==0 else f'FAIL:{r}'); s.close()"` |
| `host.docker.internal:11434` | Ollama（本地 LLM） | 同上，换端口 |
| `172.19.0.1:18931` | 网关代理 | 同上，换 IP |
| `8.8.8.8:53` | 外部 DNS | 同上，换 IP 和端口 |

## 常见故障模式

### 模式 A: 代理端口不通（connect_ex=111 或 110）
- **原因**：宿主机代理软件未启动（Clash/SSR/v2rayN/Trojan 等）
- **修复**：在 Windows 上启动代理软件
- **临时绕行**：如果 `NO_PROXY` 配置了 `host.docker.internal`，可以删除 HTTP_PROXY/HTTPS_PROXY 环境变量，让容器直连（前提是 Docker 网络层允许出站）

### 模式 B: 全部出站超时（connect_ex=110 对所有外部目标）
- **原因**：Docker Desktop 的 Hyper-V 网络层阻断出站连接；或容器 `--network` 模式受限
- **排查**：`docker inspect <container> | grep NetworkMode`；对终端容器，检查 `config.yaml` 中 `terminal.docker_extra_args`
- **修复**：`config.yaml` 中设 `terminal.docker_extra_args: ["--network=host"]` 然后 `docker compose restart`（或 `down + up -d`）；或直接重启 Docker Desktop
- **注意**：`--network=host` 让容器复用宿主机网络栈，出站问题立即解决。此改动在 `config.yaml` 中持久化，不会因容器重建丢失。执行后需要容器重启才生效。
- **⚠️ 对终端容器（nikolaik/python-nodejs）的特别说明**：此容器与 Hermes 主容器独立，默认 bridge 网络可能完全断联（TCP 8.8.8.8:53 超时、host.docker.internal 不可达）。即使主容器网络正常，工具容器仍可能无外网路由。`--network=host` 在 WSL2 + Docker Desktop 下是模拟实现，不一定对所有场景生效。终极绕行方案：Windows 手动下载→共享 volume。
- **容器内无法重启自身**：工具容器内没有 docker CLI，修改 config.yaml 后必须外部执行 `docker compose restart`。

### 模式 C: DNS 解析失败
- **原因**：Docker 内部 resolver 异常
- **修复**：在 `/etc/docker/daemon.json` 中配置 `dns: ["8.8.8.8", "1.1.1.1"]` 并重启 Docker

### 模式 D: 环境变量大小写不匹配
- **原因**：只设了 `HTTP_PROXY`（大写），`http_proxy`（小写）未设 → Python 程序不走代理
- **修复**：在 docker-compose.yml 中同时设置大小写版本

### ⚡ 模式 E: NO_PROXY 包含外网站点（新发现）

**现象**：所有外部下载（GitHub/PyPI/GitLab/BitBucket）超时，但 `host.docker.internal:18931` (代理) 和 `host.docker.internal:11434` (Ollama) 正常。

**根因**：
```
NO_PROXY=...,github.com,api.github.com,pypi.org,gitlab.com,bitbucket.org
```
这些外网站点被写进了**不走代理**的白名单。流量流向：
```
容器 → 目标在 NO_PROXY 里？ → 是 → 不走代理，直连 → Docker bridge NAT
                                                          ↓
                                                    ❌ TCP 超时
                                                    (Docker Desktop bridge 模式默认无 NAT 转发)
```
但代理端口（host.docker.internal:18931）本身不在 NO_PROXY 里，所以：
```
容器 → host.docker.internal:18931(代理) → 不在 NO_PROXY → 走代理 → ✅ 通
容器 → github.com → 在 NO_PROXY → 不走代理 → ❌ 不通
```

**诊断命令**：
```bash
echo $NO_PROXY | tr ',' '\\n' | grep -n "github\\|pypi\\|gitlab\\|bitbucket\\|gitlab"
# 如果有匹配行，说明这些站点被排除在代理之外
```

**修复**：
- **即时（容器内）**：
  ```bash
  export NO_PROXY=$(echo $NO_PROXY | tr ',' '\\n' | grep -v -E "github|pypi|gitlab|bitbucket" | paste -sd ',')
  ```
  或直接覆盖：
  ```bash
  unset NO_PROXY
  # 或设只保留内部地址
  export NO_PROXY="localhost,127.0.0.1,host.docker.internal,.local,.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,api.deepseek.com"
  ```

- **根治（修改 docker-compose.yml）**：
  找到宿主机上的 `docker-compose.yml`（可能在 WSL 或 Windows 路径），将 `NO_PROXY` 环境变量中的 `github.com,api.github.com,pypi.org,gitlab.com,bitbucket.org` 删除，然后 `docker compose down && docker compose up -d`。

- **当代理端口 18931 本身不可达时的直连绕行**：
  如果 `host.docker.internal:18931` 超时（Docker Desktop 未转发此端口），上述修复无效。改用完全绕过代理的方式：
  ```bash
  unset HTTPS_PROXY http_proxy https_proxy HTTP_PROXY
  export NO_PROXY="*"
  # 现在 curl/git 直接连接（不经过代理）
  ```
  这种方式下容器直接通过 Docker NAT 出站，2026-07-25 实测 GitHub 直连成功（`git clone --depth 1` 可拉取公开仓库）。
  **限制**：慢（~10s 才能连通），但可靠。搜索 API（`/search/repositories`）响应慢可能超时，优先用已知 URL 直接下载。

**为什么 DeepSeek API 能通？**
`api.deepseek.com` 也在 NO_PROXY 中，但宿主机的 `host_proxy.py` 以原生 socket 直连 deepseek（国内可达），且 Hermes 主容器的网络配置可能允许特定出站。工具容器（terminal 用 nikolaik/python-nodejs）的 bridge 网络则全断。**两套容器的网络权限不同。**

**为什么 DeepSeek API 能通？**
`api.deepseek.com` 也在 NO_PROXY 中，但宿主机的 `host_proxy.py` 以原生 socket 直连 deepseek（国内可达），且 Hermes 主容器的网络配置可能允许特定出站。工具容器（terminal 用 nikolaik/python-nodejs）的 bridge 网络则全断。**两套容器的网络权限不同。**

**为什么 `host.docker.internal` 能通？**
它是 Docker 内置的虚拟网卡（`192.168.65.254`），不走 bridge NAT，直通宿主机进程（Ollama / host_proxy.py）。

**后续预防**：创建任何新的 cron job 或下载任务前，先执行
```bash
echo $NO_PROXY | grep -E "github|pypi|gitlab" && echo "⚠️ 警告：外网站点被 NO_PROXY 排除" || echo "✅ NO_PROXY 无外网站点"
```

## 快速诊断脚本

```python
#!/usr/bin/env python3
"""快速网络诊断"""
import socket, os

targets = [
    ('host.docker.internal', 18931, '代理'),
    ('host.docker.internal', 11434, 'Ollama'),
    ('172.19.0.1', 18931, '网关代理'),
    ('google.com', 443, 'Google'),
]

for host, port, label in targets:
    try:
        ip = socket.gethostbyname(host)
        s = socket.socket()
        s.settimeout(4)
        r = s.connect_ex((ip, port))
        status = {0:'✅', 111:'❌ 拒绝', 110:'❌ 超时'}.get(r, f'❌ 代码{r}')
        print(f'{status} {label}: {host}:{port} → {ip}')
        s.close()
    except Exception as e:
        print(f'❌ {label}: {e}')

print('--- 环境变量 ---')
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','NO_PROXY']:
    print(f'  {k}={os.environ.get(k, "<未设置>")}')
```

## Pitfalls

1. **不要在诊断中使用 ping/curl/wget** — 这些工具在精简容器（如 `nikolaik/python-nodejs`）中不存在，会误判为"网络不通"
2. **不要在诊断中使用 bash /dev/tcp** — 在受限 Docker 网络中，`/dev/tcp` 的 TCP 连接会挂死（不返回超时），导致 terminal 命令超时阻断
3. **`host.docker.internal` 的 IP 不代表宿主机** — Docker Desktop 把它映射到 `192.168.65.254`（内部网关），不是 Windows 宿主机的真实 IP。真正的宿主机网络要通过网关或 `--network=host` 访问
4. **重置 netfilter 有时能解** — 在 Windows 上运行 `wsl --shutdown` 然后重启 Docker Desktop 能解决部分网络粘连问题
5. **NO_PROXY 的陷阱** — 不但要查 NO_PROXY 里有哪些内容，还要**逐个检查每个站点是否本应走代理**。常见错误是把外网下载站点（GitHub/PyPI）也加到 NO_PROXY 里，导致"代理端口通但下载不通"的诡异现象
6. **两套容器网络不同** — Hermes 主容器和 terminal 工具容器（nikolaik/python-nodejs）是独立的容器实例，网络配置可能完全不同。主容器能访问 host.docker.internal，工具容器可能不能。诊断时必须说明是针对哪个容器。
