---
name: finance-expert
description: 金融炒股专家技能 — 行情查询、财报分析、技术面分析、ETF研究、策略回测、学习复习一体化
category: finance
triggers:
  keywords:
    - 股票行情
    - 炒股
    - 基金
    - ETF
    - 大盘
    - 走势分析
    - 行业
    - 板块
    - 个股
    - 投资策略
    - 财报
    - 技术分析
    - 基本面
    - K线
    - 牛熊
    - 抄底
    - 止损
    - 技术指标
    - 回测
    - 模拟
    - 复盘
    - 复盘交易
    - 买点
    - 卖点
    - 成交量
    - 均线
    - 市盈率
    - ROE
    - 北向资金
    - 新闻资讯
    - 财经消息
    - 量化
    - 策略
    - 学习炒股
    - 入门
    - 新手
    - 金融知识
platforms: [linux]
related_skills:
  - web-connectivity
  - dependency-tracker
  - skill-creation-rules
  - data-retention
---

# 金融炒股专家技能 v1

## 概述

本技能将一个普通的 Hermes Agent 变身为**金融/炒股专家**，具备六大核心能力：

1. **📊 行情数据** — 实时/延时获取全球主要指数、个股、ETF 行情（腾讯/新浪/Yahoo 多源）
2. **📰 最新消息** — 抓取财经新闻、公告、市场动态
3. **📚 知识体系** — 内置入门三大书摘要 + 股票/ETF/财报/技术分析完整参考
4. **🎯 策略回测** — 简单量化策略的历史回测引擎
5. **🔄 学习迭代** — 交易复盘+知识复习+模拟交易的闭环系统
6. **⚡ 工具集成** — 与 Hermes 现有工具链（terminal、cron、execute_code）无缝协作

---

## 边界条件

### 入口条件
- 用户询问股票、基金、ETF 相关话题
- 用户要求获取最新行情
- 用户要求分析走势
- 用户要求学习炒股知识
- 用户要求回测策略
- 用户要求最新的财经消息
- 用户要求分析财报

### 跳过条件（一条即跳过）
- [ ] 用户明确要其他领域的知识（如编程、音乐）
- [ ] 来源数据 API 全部不可用（网络断连）
- [ ] 用户仅闲聊与金融无关

### 中止条件（执行中，一条即停）
- [ ] 用户切换话题
- [ ] 持续 2 次 API 请求失败且无替代数据源
- [ ] 回测脚本超过 30 秒无响应
- [ ] 连续 3 次 return None

---

## 决策矩阵

| 场景 | 行动 | 工具链 | 产出 |
|------|------|--------|------|
| 用户问"XX行情怎么样" | 调用行情脚本获取最新数据→分析涨跌 | `terminal(scripts/fetch_stock.py)` + 推理 | 行情快报（含涨跌幅+支撑/压力位） |
| 用户问"最近有什么消息" | 加载新闻抓取→提取重磅消息 | `terminal(scripts/fetch_news.py)` + 筛选 | 财经要闻摘要 |
| 用户问"XX公司的财报如何" | 获取季度数据→关键指标分析 | `terminal(scripts/analyze_report.py)` + 推理 | 财报解读（含ROE/利润率/负债率） |
| 用户问"这个策略怎么样" | 输入策略参数→跑回测→输出绩效 | `read_file(templates/strategy-backtest.md)` + `terminal(scripts/backtest.py)` | 回测报告（年化/回撤/夏普比） |
| 用户问"怎么入门/学习" | 载入 skill 参考文档→按学习路径输出 | `skill_view(file_path=references/books/*.md)` | 学习路径+当前章节精华 |
| 用户问"这个指标是什么意思" | 查阅基础知识参考→解释 | `skill_view(file_path=references/*)` | 指标解释+使用场景 |
| 用户要求"模拟一下" | 按模板启动模拟交易练习 | `skill_view(templates/*)` + 交易练习 | 模拟交易回合+打分 |
| 要求获取具体个股 | fetch_stock.py 单股模式→分析 | `terminal(scripts/fetch_stock.py -s <CODE>)` | 个股详细数据+简评 |

---

## 原子步骤

### Step 1: 识别用户意图

**输入**：用户消息
**工具**：推理（无需外部工具）
**操作**：
1. 判断用户属于以下哪类请求：
   - 行情类（"XX现在什么价""大盘怎么样"）
   - 消息类（"最近有什么新闻"）
   - 学习类（"什么是PE""怎么读财报"）
   - 分析类（"XX涨了怎么看""STOP什么意思"）
   - 回测类（"帮我测一个均线策略"）
   - 综合类（多个意图混合）
2. 根据意图类型选取对应分支

**验证**：确定主意图（如模糊则用 clarify 询问）

**产出**：意图分类 + 执行分支

---

### Step 2: 执行数据/知识获取

**输入**：意图分类
**操作与产出**：

- **分支A（行情）** → `terminal("python3 /opt/data/skills/finance/finance-expert/scripts/fetch_stock.py")`
- **分支B（消息）** → `terminal("python3 /opt/data/skills/finance/finance-expert/scripts/fetch_news.py")`
- **分支C（学习）** → `skill_view(name="finance-expert", file_path="references/<主题>.md")`
- **分支D（回测）** → 见 Step 2a

**验证**：工具调用 exit_code == 0，输出非空

---

### Step 2a: 策略回测分支

**输入**：用户描述的策略规则
**工具**：`terminal` + `read_file`
**操作**：
1. 引导用户按模板提供策略参数：标的、买入条件、卖出条件、资金、周期
2. 拼装参数调用 `scripts/backtest.py`
3. 回读输出

**⚠️ 已知局限**：
- 腾讯API **仅A股/港股有完整历史K线**，美股代码只能拿到1天数据
- 回测只支持A股/港股标的，美股回测请用 `--strategy hold` 做单日测试
- 容器环境无numpy，标准差计算为纯Python手动实现
- 详细参考 `skill_view(name="finance-expert", file_path="references/data-sources.md")`

**验证**：回测报告完整（含年化收益、最大回撤、夏普比、交易次数）

---

### Step 3: 加工输出

**输入**：Step 2 的原始数据
**操作**：
1. 对行情数据：计算当日涨跌幅、周涨跌幅、对比同期指数
2. 对新闻数据：按重要性排序，去重
3. 对回测报告：解读关键指标（年化>15%算好，回撤<20%算稳）
4. 对学习内容：用类比+实例解释

**验证**：输出有数据支撑，不凭空猜测

---

### Step 4: 固化学习

**输入**：本次交互的关键发现
**工具**：`memory` + `fact_store`
**操作**：
1. 如果用户问了某个股票→`fact_store(action='add', content='用户关注XX股票')`
2. 如果涉及重要知识→记录到 memory（用户偏好、知识盲区等）
3. 定期复盘时可用这些数据做个性化推荐

**验证**：memory 可用

---

## 工具/Skill 联动表

| 步骤 | 调用的工具 | 读取的文件 | 写入的文件 | 依赖的 skill |
|------|-----------|-----------|-----------|-------------|
| Step 1 | （推理） | — | — | — |
| Step 2 行情 | `terminal` | `scripts/fetch_stock.py` | — | `web-connectivity` |
| Step 2 消息 | `terminal` | `scripts/fetch_news.py` | — | `web-connectivity` |
| Step 2 学习 | `skill_view` | `references/*.md` | — | — |
| Step 2 回测 | `terminal`+`read_file` | `scripts/backtest.py`+`templates/*` | 回测输出 | `dependency-tracker` |
| Step 3 | （推理） | — | — | — |
| Step 4 | `memory`+`fact_store` | — | 记忆系统 | — |

---

## 反馈回路

### 文件写后验证
每个 `write_file` → `read_file` 回读确认

### 行情数据验证
- 多源交叉验证（腾讯 vs Yahoo vs 新浪）
- 如果两个源数据一致（差异<0.5%）→ 可信
- 如果差异大 → 以腾讯为主（国内用户）

### 学习进度追踪
在 `fact_store` 中记录用户已学内容：
```json
{
  "action": "add",
  "content": "用户已学: PE/PB/ROE 概念",
  "entity": "用户金融学习进度"
}
```

### 迭代上下文
- 对于复杂策略回测：保存参数到 `trading/strategies/<策略名>/params.json`
- 下次修改可以增量迭代

### 降级/死路
- 所有行情 API 不通 → 告知用户网络问题，提供行情数据分析建议
- 回测参数填写不全引导用户补完整
- 美股回测请求 → 告知局限（腾讯API仅1天数据），引导用A股或单日分析
- 新闻源单一故障 → 自动切换备用源（新浪→雅虎→东方财富）
- 新书/知识点先汇总到 references/pending-knowledge.md

### ⚠️ 数据脚本构建验证（2026-07-26 实测教训）
**这是一个关键陷阱**：腾讯API等外部数据源的**字段索引不保证稳定**，API升级时会增减/重排字段。

**每次编写/修改数据脚本前，必须先做**：
1. 跑一次原始API响应，提取所有字段 → 确认索引实际对应
2. 验证关键字段的合理性（如茅台PE≈20，市值≈1.6万亿）
3. 确认新闻等字段的时间格式（Unix时间戳需格式化）
4. 写完后跑完整脚本验证输出正确

**参考文档**：`skill_view(name="finance-expert", file_path="references/tencent-api-fieldmap.md")`

**典型失败模式**：
| 症状 | 根因 | 预防 |
|------|------|------|
| 行业显示数字 | parts[57]是行业指数代码，不是名 | 先dump raw API |
| 市值单位错 | parts[45]单位不是"万" | 用已知股票验证 |
| 新闻显示Unix戳 | ctime是Unix时间戳未格式化 | 检查字段类型 |

---

## 技能内文件说明

```
skills/finance/finance-expert/
├── SKILL.md                       ← 本文件（技能核心）
├── references/
│   ├── books/
│   │   ├── easy-investing.md      ← 《投资中最简单的事》精华
│   │   ├── random-walk.md         ← 《漫步华尔街》精华
│   │   └── stock-operator.md      ← 《股票大作手回忆录》精华    
│   ├── data-sources.md            ← 数据源局限与已知坑
│   ├── tencent-api-fieldmap.md    ← ⚠️ 腾讯API字段映射验证表
│   ├── stock-basics.md            ← 股票基础概念
│   ├── etf-guide.md               ← ETF 入门指南
│   ├── financial-statements.md    ← 财报阅读指南
│   └── technical-analysis.md      ← 技术分析基础
├── templates/
│   ├── strategy-backtest.md       ← 策略回测填写模板
│   └── trading-journal.md         ← 交易日志模板
└── scripts/
    ├── fetch_stock.py             ← 行情数据获取
    ├── fetch_news.py              ← 财经新闻获取
    ├── backtest.py                ← 策略回测引擎
    └── analyze_report.py          ← 财报指标解析
```
