---
name: config-unification
description: 配置统筹方法论。覆盖四个入口：新建（决策框架）、修改（覆盖链审计）、故障（症状反向追溯）、技能自修复（缺口发现→技能更新）。遇到配置/网络/跨文件问题时自动加载。
category: architecture
platforms: [linux, windows]
related_skills: [hermes-optimization, skill-creation-rules]
triggers:
  keywords:
    # 新建场景
    - 新建配置
    - 创建文件
    - 新项目
    - 初始化
    - 架构设计
    - 新增模块
    - 扩展功能
    - 加个配置
    - 写个新
    - 新增组件
    - 引入新服务
    # 修改场景
    - 更新配置
    - 修改配置
    - 迁移
    - 重构
    - 升级
    - 改一下
    - 调整
    - 变更
    - 配置冲突
    - 变量覆盖
    - 跨文件
    - 环境变量
    - 多文件关联
    - 统一变量
    - 配置统筹
    - 单事实来源
    - override chain
    - configuration topology
    - 覆盖链
    - 依赖关系
    - 冲突
    # 故障场景
    - 排查
    - 诊断
    - 调试
    - 断网
    - 连不上
    - 连不了
    - 无法连接
    - 无网络
    - 不通
    - 报错
    - 异常
    - 不工作
    - 挂了
    - 超时
    - 修一下
    - bug
    - 错误
    - 问题
    - 故障
    - 网络不通
    - 不能访问
    # 通用
    - SSOT
    - 配置管理
    - 最佳实践
    - CONTEXT.md
    - 自修复
    - 技能缺口
    - 技能优化
    - 技能更新
    - 这个技能
    - 不适用
    - 没有覆盖
    - 缺了
    - 漏了
    - 不对啊
    - 不符合
    - 上下文文档
    - 统筹
    - 隐患
    - 坑
    - 注意
---

# Configuration Unification — 配置统筹方法论 v2

## 核心问题

复杂系统中，同一个变量可能在 N 层中分别定义。改了一层，另外一层没改，就产生冲突。

```
典型例子：
基础镜像: HTTP_PROXY=""（空字符串）、NO_PROXY="*"
docker-compose: 未提及 → 继承基础镜像的值
Docker Desktop 引擎: 试图注入 http.docker.internal:3128
→ NO_PROXY=* 说"别用代理"，引擎说"都用代理"
→ 两相矛盾 → 请求挂死
```

此类问题不具备特异性，是 **配置系统层级设计** 的通用缺陷。
任何一个涉及"多层覆盖"的系统都会有这种问题，只是迟早。

---

## 三个入口

本技能提供三条独立的进入路径，取决于你当前在做的事：

```
你正在做什么？
├── 创建新东西 → 入口 A: 新增工作流
├── 改现有的东西 → 入口 B: 修改工作流
├── 发现有问题 → 入口 C: 故障回溯
└── 技能本身有缺口 → 入口 D: 技能自修复
```

---

# 入口 A: 新增工作流

> 场景：你要加一个新的配置项、一个新的文件、一个新的组件。
> 目标：从一开始就避免冲突，在正确的层放正确的东西。

## A1. 命名审计

新变量命名前，先检查它是否**已存在于**其他层：

```
□ 基础镜像中是否已有同名变量？
  命令: docker inspect <image> --format '{{range .Config.Env}}{{.}}{{"\n"}}{{end}}'
  结果: ________

□ 当前项目的其他配置文件中是否已有？
  搜索: grep -r "VAR_NAME" . --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env"
  结果: ________

□ Host 级配置是否定义了同名变量？
  检查: ~/.wslconfig, ~/.docker/daemon.json, Docker Desktop settings
  结果: ________

□ 大小写变体是否已被占用？
  例如：HTTP_PROXY / http_proxy / HttpsProxy
  结果: ________
```

## A2. 层级选择

根据新配置的性质，选择合适的层级：

| 层级 | 适合放的配置 | 文件 | 例子 |
|------|------------|------|------|
| **Layer Host** | 全局基础设施参数 | `~/.wslconfig`, `~/.docker/daemon.json` | DNS 服务器、WSL2 内存限制 |
| **Layer Image** | 容器镜像本应知的属性 | `Dockerfile` ENV | 安装路径、默认语言 |
| **Layer Compose** | 编排相关的静态属性 | `docker-compose.yml` `environment:` | 端口映射、容器名称、健康检查 |
| **Layer Env** | 运行时选择（可变的） | `.env` | API keys、token、环境标识 |
| **Layer Config** | 应用行为逻辑 | `config.yaml` | 超时时间、模型选择、特性开关 |
| **Layer Runtime** | 临时调试或修复 | `entrypoint` shell 命令 | unset 冲突变量、临时覆盖 |

**决策树**：
```
这个值是否会随部署环境变化？
├── 是 → 放 .env（Layer Env）
└── 否
    ├── 这是基础设施全局的？
    │   ├── 是 → 放 host 级配置
    │   └── 否
    ├── 这是容器应该自带的？
    │   ├── 是 → 放 Dockerfile（Layer Image）
    │   └── 否
    ├── 这是编排相关的？
    │   ├── 是 → 放 docker-compose（Layer Compose）
    │   └── 否
    └── 这是应用行为？
        ├── 是 → 放 config.yaml（Layer Config）
        └── 否 → 需要重新考虑：它到底是什么？
```

## A3. 实施与注册

1. 在选定的层级文件中写入新配置
2. **立即** 将所有其他层级中可能继承/覆盖这个变量的地方检查一遍
3. 更新 CONTEXT.md 的变量注册表
4. 重建/重启后验证最终值

---

# 入口 B: 修改工作流

> 场景：你要改一个已有的配置项。
> 目标：同一变量的所有层都同步修改，不留不一致。

## B1. 定位

在 CONTEXT.md 中找到要修改的变量：

```
变量名 → 查 CONTEXT.md 变量注册表
         → 确认它的源、覆盖链、影响范围
         → 列出所有涉及的文件
```

如果 CONTEXT.md 中没有（说明之前没记录），则先执行完整追踪：

```
docker inspect <image> → 检查基础镜像
grep -r "VAR" .        → 检查项目文件
检查 host 级配置       → 检查引擎层
```

## B2. 覆盖链修改

对每一层逐层修改：

```
Layer 0 (基础镜像):  不可改 → 需要在 Layer 1+ 覆盖
Layer 1 (compose):   修改或添加 environment: 项
Layer 2 (env_file):  修改 .env 中的值
Layer 3 (entrypoint): 修改 unset / export 命令
Layer 4 (进程):      最后根据 entrypoint 逻辑确定最终值
```

**重要原则**：改完某一层后，如果没有显式覆盖，下层继承的是上层的**修改后的值**。但如果你改的是 .env，docker-compose 没有引用这个变量，那改了也没用。

**命名一致性**：大写和小写版本必须同步修改。
如果改 `HTTP_PROXY`，也必须检查 `http_proxy`。

## B3. 验证

```bash
# 容器重建后（不要用 docker exec env）
docker exec <container> sh -c 'cat /proc/1/environ | tr "\0" "\n" | grep <VAR>'

# 确认值正确
docker exec <container> sh -c 'echo "${<VAR>:?未设置}"'
```

## B4. 更新记录

CONTEXT.md 修改历史 + 注册表 + 陷阱（如果有新发现）。

---

# 入口 C: 故障回溯

> 场景：系统出问题了，你需要定位是不是配置引起的。
> 目标：从症状出发，逆向追踪到变量，找到冲突的层。

## C1. 症状定位

```
症状: __________________________________
  例: OpenAI API 请求超时

发生位置: __________________________________
  例: Hermes 容器内调用 requests.post(openai)

影响的功能: __________________________________
  例: 所有需要调用 OpenAI 的工具
```

## C2. 故障二分法

判断是配置问题还是其他问题：

```
故障可能性
├── 代码问题：功能最近没改过但突然坏了 → 可能是外部变化
│   ├── 外部 API 挂了 → 检查服务状态页
│   └── 环境变了（Docker 升级/WSL2 更新） → 检查变更日志
└── 配置问题：某些东西改了配置后坏的
    ├── 环境变量改了？
    ├── 网络/代理配置改了？
    ├── 新文件引用了冲突变量？
    └── 基础镜像更新了？
```

## C3. 变量级定位

从症状反推可能受影响的变量：

```
症状 → 影响子系统 → 子系统依赖的配置

例1:
  OpenAI 超时
  → HTTP 出站
  → 相关变量: HTTP_PROXY, HTTPS_PROXY, NO_PROXY, http_proxy, https_proxy
  → 相关配置: DNS 设置, Docker Desktop 代理, 网络模式

例2:
  容器启动失败
  → 容器初始化
  → 相关变量: ENTRYPOINT, CMD, 环境变量
  → 相关配置: docker-compose.yml 格式, 镜像存在性

例3:
  数据库读写错误
  → 数据持久化
  → 相关配置: volume 挂载路径, 文件权限, 数据库路径
```

## C4. 对照验证

对每个可能变量，执行**对照测试**（隔离法）：

```
测试1（基线）: 保持当前状态运行 → 记录结果
测试2（改一个变量）: unset / 修改变量 A → 结果变了？
测试3（改另一个）: unset / 修改变量 B → 结果变了？
测试4（完全清除）: 清除所有可疑变量 → 结果变了？
```

**本次真实案例**：
```
测试1: HTTP_PROXY="" NO_PROXY="*" → OpenAI 超时
测试2: 只 unset NO_PROXY          → OpenAI 421 in 0.99s ← 找到！
测试3: NO_PROXY=* + 显式代理      → OpenAI 超时
测试4: 全部 unset                  → OpenAI 421 in 1.3s
```
**⚠️ docker exec 陷阱**：
`docker exec` 启动的不是容器主进程的 shell，而是一个**全新的 shell 进程**。这个新 shell 继承的是 **Docker 守护进程存储的默认环境**，而不是 PID 1 的实际环境。

这意味着：
- 即使 entrypoint 已经 `unset` 了某个变量，`docker exec env` 仍然会显示它（Docker 守护进程的记录未被更新）
- 用 `docker exec` 做对照测试时，`unset VAR` 只影响这个新 shell，不影响主进程
- 但如果排查"容器为什么不工作"，`docker exec` 的测试结果仍然有价值——它模拟了子进程继承默认环境时的行为

**正确做法**：
- 查主进程真实值 → `cat /proc/1/environ | tr "\0" "\n" | grep VAR`
- 做对照测试 → 确保 unset + curl 在同一个 shell 命令中执行
- 修复后验证 → 检查 PID 1 的环境，而非 `docker exec env`
- 区分"docker exec 里测不通"和"容器主进程实际不通"——两者不一定等价


## C5. 覆盖链逆向追溯

找到问题变量后，逆向追溯它被设置的每一层：

```yaml
Variable: NO_PROXY
  Layer 0 (基础镜像):  "NO_PROXY=*" ← 问题来源
  Layer 1 (compose):   未提及，继承 Layer 0
  Layer 2 (env_file):  未提及，继承 Layer 0
  Layer 3 (entrypoint): unset NO_PROXY ← 修复点
  Layer 4 (PID 1):     不存在 ✅
  
根因: Layer 0 设了 NO_PROXY=*，没有被任何上层覆盖
修复: 在 Layer 3 (entrypoint) 中 unset
```

**常见模式**：
- 基础镜像设了但上层不知道 → 修在 entrypoint unset
- 用户手工改了 host 级配置 → 修在对应配置
- Docker 升级改写了默认行为 → 显式覆盖

## C6. 陷阱捕获

故障修复后，将新的发现记录为陷阱：

```
新陷阱:
  变量: ____________
  冲突模式: ____________（如: 空串 ≠ 未设置）
  表现: ____________
  修复: ____________
  添加到 CONTEXT.md 变量注册表和陷阱列表
```

---

---

# 入口 D: 技能自修复

> 场景：你在使用本技能的 A/B/C 入口时，发现技能描述的步骤或场景与实际情况不符。
> 目标：识别缺口，补充技能，让技能在下一次使用时覆盖这个场景。

## 什么时候该走 D？

```
使用本技能时出现以下情况之一：
□ 技能说的排查步骤跟你遇到的不匹配
   例: C4 说"做对照测试"，但你发现 docker exec 的环境跟预期不符
□ 你发现了一个技能没有覆盖的新场景
   例: 基础镜像 ENV 空字符串 vs unset 的行为差异
□ 技能给出的建议在你的环境中不成立
□ 你补充了一个新陷阱，它应该作为通用知识被固化在技能里
```

## D1. 缺口定位

描述你遇到的情况，和技能描述的有什么不同：

```
技能描述的: __________________________________
  例: C4 对照测试 — 在 shell 中 unset VAR 然后测试

实际情况: __________________________________
  例: docker exec 启动的是新 shell，其环境与 PID 1 不同
      即使 entrypoint 已经 unset，docker exec 仍然显示旧值

差异本质: __________________________________
  例: 技能没有区分"容器默认环境"和"进程实际环境"
```

## D2. 根因判断

判断这个缺口是**技能本身的疏漏**，还是**环境特殊性**：

```
□ 技能疏漏 — 所有 Docker 容器都有这个问题，不是平台特例
  修复: 在技能中加入通用提示

□ 环境特殊性 — 仅在特定平台/版本下出现
  修复: 在技能中加入平台限定说明

□ 知识更新 — 工具或平台升级后旧知识不再适用
  修复: 更新技能中过时的部分
```

## D3. 缺口记录

将发现的缺口形成一个**可添加到技能中的知识片段**：

```
新增知识点:
  位置: ________________________________（哪个章节？C4/A2/B3？）
  类型: [陷阱提示 / 步骤补充 / 边界条件 / 触发词]
  内容:
    ________________________________
    ________________________________
    ________________________________
```

## D4. 技能更新

执行修改：

```
□ 在 SKILL.md 中找到目标位置
□ 插入新的知识点
□ 确认格式与周围一致
□ 检查触发词是否需要同步扩展
□ 更新版本号
```

**本次应用 D 的实例**：本技能在 v2 首次发布后，用 C 流程复盘了真实故障。
复盘过程中发现 `docker exec` 的环境继承行为与 C4 的描述不符，于是：
1. D1 定位：C4 没区分"默认环境"和"进程实际环境"
2. D2 根因：通用 Docker 行为，不是平台特例 → 技能疏漏
3. D3 记录：在 C4 后加"docker exec 陷阱"，在 C5 后加"验证最终值"复查
4. D4 更新：已应用

---

## 覆盖链参考模板

```
Layer Host:  ~/.wslconfig, ~/.docker/daemon.json, Docker Desktop settings
Layer 0:     基础镜像 Dockerfile ENV
Layer 1:     docker-compose.yml environment:
Layer 2:     docker-compose.yml env_file → .env
Layer 3:     entrypoint shell (sh -c "...")
Layer 4:     entrypoint unset (变量被移除)
Layer 5:     exec 替换 shell 后 → /proc/1/environ (最终值)
```

**关键洞察**：
- `变量=""`（空字符串）≠ `变量`（不存在的变量）
- `UNSET`（bash unset）≠ `变量=""`（bash VAR=""）
- `docker exec env` 显示的是 Docker 的默认环境，不是 PID 1 的实际环境
- 覆盖链越长，变量行为越不可预测。理想长度 ≤3 层。

---

## CONTEXT.md 模板

```markdown
# CONTEXT — [Project Name] 项目上下文文档

## 1. 配置拓扑总览
（文件结构图，标注所有配置源）

## 2. 变量注册表
（表格：变量名 | 源 | 默认值 | 最终值 | 覆盖链长度 | 影响范围）

## 3. 覆盖链
（每层来源及优先级，每层的能力和限制）

## 4. 模块依赖关系
（启动链、文件依赖图、调用链）

## 5. 已知陷阱
（已发现的冲突模式，按严重程度排列）

## 6. 修改历史
（日期 | 修改内容 | 影响文件 | 涉及变量）
```

---

## 边界条件

### 入口条件（满足任一即触发）
- 正在创建新的配置项或文件
- 正在修改已有配置
- 遇到了难以排查的故障
- 观察到"改了这里但那里没生效"的现象
- 用户说了任何触发关键词

### 出口条件
- 修改场景：8步修改协议已通过（见 CONTEXT.md）
- 新建场景：命名审计 + 层级选择已做完，CONTEXT.md 已更新
- 故障场景：根因定位到具体层和变量，陷阱已记录

### 已知不适用
- 纯前端状态管理（有更专门的工具）
- 单文件、单层的简单项目

---

## 通用原则

1. **显式优于隐式**：不要依赖"继承默认值"
2. **空串 ≠ 未设置**：始终区分 var="" 和 var 不存在
3. **大小写同步**：HTTP_PROXY 和 http_proxy 必须一致
4. **验证最终值**：检查 /proc/<pid>/environ，不用 docker exec env
5. **每次修改更新 CONTEXT.md**：过时的文档比没有更危险
6. **备份后再修改**：修改配置前确保有可恢复的快照
7. **项目启动时即建立 CONTEXT.md**：事后补极其困难
8. **单事实来源**：每个变量只在唯一一处定义预期值
9. **对照测试**：隔离变量时一次只改一个

---

## 相关参考

- [env-override-chain-analysis](references/env-override-chain-analysis.md) — 本次排查的完整实录
- [hermes-optimization 网络诊断](../hermes-optimization/references/network-diagnosis.md) — 容器网络故障诊断
- [CONTEXT.md](../../../CONTEXT.md) — 本项目实例
- [skill-creation-rules](../../meta/skill-creation-rules/SKILL.md) — 技能创建规则



