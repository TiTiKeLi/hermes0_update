 # 环境变量覆盖链分析 — Hermes Docker 代理变量排查实录
 
 > 此文档是 config-unification 方法论的具体案例。
 > 记录了我们如何追踪、定位、修复 NO_PROXY=* 导致的容器网络不可用问题。
 
 ## 问题现象
 
 Hermes Docker 容器中，Baidu/DeepSeek 可访问，但 OpenAI/GitHub 超时。
 
 ## 排查过程
 
 ### Step 1: 列出所有配置源
 
 | # | 源 | 文件 | 影响方式 |
 |---|-----|------|---------|
 | 0 | 基础镜像 hermes-agent:with-deps | 构建时 Dockerfile ENV | `docker inspect` 可见 |
 | 1 | docker-compose.yml | `environment:` | 编译时注入 |
 | 2 | .env | `env_file:` | 编译时注入（优先级低于 environment） |
 | 3 | Docker Desktop 引擎 | settings-store.json | 网络层 iptables 拦截 + 代理注入 |
 | 4 | entrypoint shell | command: unset | 运行时清除 |
 | 5 | 进程 environ | /proc/1/environ | 实际生效值 |
 
 ### Step 2: 逐层追踪 HTTP_PROXY
 
 ```yaml
 Variable: HTTP_PROXY
   Layer 0 (基础镜像):  "HTTP_PROXY=" — 空字符串
   Layer 1 (compose):   未提及 — 保持 Layer 0
   Layer 2 (env_file):  未提及 — 保持 Layer 0
   Layer 3 (Docker引擎): 试图注入 http.docker.internal:3128
                         — 但被 Layer 0 的空值阻止
                         — 引擎以为"已设置"，不覆盖
                         — 但网络层拦截规则仍生效
   Layer 4 (entrypoint): unset HTTP_PROXY — 从环境移除
   Layer 5 (PID 1):     不存在 ✅
 ```
 
 ```yaml
 Variable: NO_PROXY
   Layer 0 (基础镜像):  "NO_PROXY=*" — 所有地址绕过代理
   Layer 1 (compose):   未提及 — 保持 Layer 0
   Layer 2 (env_file):  未提及 — 保持 Layer 0
   Layer 3 (Docker引擎): NO_PROXY=* 告诉应用层"不走代理"
                         — 但引擎层仍拦截并重定向流量
                         — 矛盾：应用层直连，引擎层拦截
   Layer 4 (entrypoint): unset NO_PROXY — 从环境移除
   Layer 5 (PID 1):     不存在 ✅
 ```
 
 ### Step 3: 对比测试证明
 
 | 测试 | HTTP_PROXY | NO_PROXY | OpenAI 结果 |
 |------|-----------|----------|------------|
 | 初始状态 | `""`(空) | `*` | **超时** (6s) |
 | 只 unset NO_PROXY | `""`(空) | 未设置 | **421 in 0.99s** |
 | NO_PROXY=* + 显式代理 | `http://host.docker.internal:3128` | `*` | **超时** (6s) |
 | 完全 unset 所有 | 未设置 | 未设置 | **421 in 1.3s** |
 
 **关键发现**：unset NO_PROXY 比设置正确的 HTTP_PROXY 更重要。
 
 ### Step 4: Docker Desktop 引擎层代理
 
 即使环境变量正常，Docker Desktop 的引擎层代理仍可能干扰：
 
 ```json
 // ~/AppData/Roaming/Docker/settings-store.json
 {
   "OverrideProxyHTTP": "http://127.0.0.1:12334",
   "OverrideProxyHTTPS": "http://127.0.0.1:12334",
   "ProxyHTTPMode": "system"
 }
 ```
 
 `ProxyHTTPMode: "system"` 表示 Docker 尝试从 Windows 系统代理设置获取参数。
 即使代理变量为空/未设置，引擎层仍可能拦截出站流量。
 
 ### Step 5: 修复
 
 修复点在 entrypoint shell 中：
 
 ```bash
 # docker-compose.yml command:
 unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy
 python3 /opt/data/gui.py &
 exec hermes gateway run
 ```
 
 为什么不是 docker-compose `environment:`？
 - 基础镜像 ENV 有 `HTTP_PROXY=`（空字符串）
 - docker-compose `environment: HTTP_PROXY=` 仍然设成空字符串
 - 空字符串 ≠ unset。部分库行为不同
 - 只有 shell `unset` 能完全移除变量
 
 ## 排查工具速查
 
 ### 查看基础镜像的 ENV
 ```bash
 docker inspect <image> --format '{{range .Config.Env}}{{.}}{{"\n"}}{{end}}'
 ```
 
 ### 查看容器进程的实际环境（非 docker exec）
 ```bash
 docker exec <container> sh -c 'cat /proc/1/environ | tr "\0" "\n" | grep -i proxy'
 ```
 
 ### 测试不同变量组合
 ```bash
 docker exec <container> sh -c 'unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy; curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://api.openai.com'
 ```
 
 ### 对比测试（对照组思维）
 ```
 测试1 → 当前状态 → 基线
 测试2 → 改 1 个变量 → 隔离变量 A 的影响
 测试3 → 改另 1 个 → 隔离变量 B 的影响
 测试4 → 全清 → 确认最大影响
 ```
 
 ## 教训总结
 
 1. **基础镜像 ENV 是隐形的"默认层"**——修改时必须先检查基础镜像的配置
 2. **NO_PROXY=* 是危险的**——它阻止了所有代理机制，即使底层有其他代理规则在生效
 3. **docker-compose.yml 应"显式覆盖"所有基础镜像中已知冲突的变量**，包括空值
 4. **shell unset 是唯一能完全移除变量的方式**——docker-compose `environment:` 和 `env_file` 都只能设值
 5. **macOS/Linux 上无此问题**——Docker Desktop 的引擎层代理是 Windows/WSL2 特有的
 6. **每次容器重建后应验证环境**——使用 `/proc/<pid>/environ` 而非 `docker exec env`
