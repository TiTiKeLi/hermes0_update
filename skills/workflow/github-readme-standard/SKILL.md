 ---
 name: github-readme-standard
 description: GitHub README 编写标准 — 参考 React/Vue/VS Code 等顶级项目的 README 结构。包含必需节、可选节、徽章系统、快速开始模板。
 category: workflow
 platforms: [windows, linux]
 related_skills:
   - git-version-control
   - github-project-management
   - skill-creation-rules
 triggers:
   keywords:
     - README
     - readme
     - 项目介绍
     - 文档
     - 仓库说明
     - 编写文档
     - github 页面
     - 项目主页
     - 开源项目
 ---
 
 # GitHub README Standard — 顶级项目 README 编写标准 v1
 
 参考项目: React, Vue, VS Code, Linux Kernel, GitHub Docs, Standard Readme
 
 ## 必需节
 
 ### 1. 项目标题 + 一行描述
 
 ```
 # 项目名称
 > 一行描述项目是什么、解决什么问题。
 ```
 
 ### 2. 徽章（Badges）
 
 放在标题下方，一行展示项目状态：
 
 ```
 ![build](...) ![version](...) ![license](...) ![PRs welcome](...)
 ```
 
 常见徽章: 构建状态、版本号、许可证、PR欢迎、代码覆盖率、下载量。
 
 ### 3. 简介（Introduction）
 
 2-3 段说明项目的核心价值、解决什么问题、跟同类项目的区别。
 
 ### 4. 快速开始（Quick Start）
 
 用户复制粘贴就能跑起来的最小步骤。代码块必须可直接执行。
 
 ### 5. 安装（Installation）
 
 详细安装步骤，包含前置依赖、系统要求、配置步骤。
 
 ### 6. 使用（Usage）
 
 常用操作示例，代码块 + 说明。
 
 ### 7. 许可证（License）
 
 明确许可证类型，链接到 LICENSE 文件。
 
 ## 推荐节
 
 | 节 | 适用场景 | 参考项目 |
 |-----|---------|---------|
 | 目录（Table of Contents） | README 超过 200 行 | 几乎所有大项目 |
 | 架构（Architecture） | 项目结构复杂 | VS Code |
 | API | 提供 API 接口 | React, Vue |
 | 贡献指南（Contributing） | 接受 PR | React, VS Code |
 | 行为准则（Code of Conduct） | 社区项目 | 所有 CNCF 项目 |
 | 致谢（Acknowledgments） | 有依赖或灵感来源 | Vue |
 | FAQ | 常见问题 | 各类项目 |
 | 路线图（Roadmap） | 有明确规划 | 框架类项目 |
 
 ## 格式规则
 
 ```
 □ 标题: # H1 = 项目名, ## H2 = 主要章节, ### H3 = 子章节
 □ 代码块: 指定语言标识, 可复制执行
 □ 列表: 无序列表 -, 有序列表 1.
 □ 表格: 对齐清晰, 表头加 ---
 □ 链接: 相对路径链接到仓库内部文件
 □ 图片: 使用相对路径或 CDN
 □ 引用: 使用 > 引用外部说明
 ```
 
 ## 长度规范
 
 | README 规模 | 行数 | 适用 |
 |------------|------|------|
 | 微型 | ≤50 行 | 个人小工具, 脚本 |
 | 标准 | 50-200 行 | 库, 框架, 工具 |
 | 大型 | 200-500 行 | 平台级项目 (VS Code) |
 
 ## 参考来源
 
 - [standard-readme](https://github.com/standard/readme) — README 规范
 - [React README](https://github.com/facebook/react) — 框架级示范
 - [Vue README](https://github.com/vuejs/vue) — 生态级示范
 - [VS Code README](https://github.com/microsoft/vscode) — 平台级示范
