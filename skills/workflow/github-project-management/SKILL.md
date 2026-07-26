 ---
 name: github-project-management
 description: GitHub 项目管理 — 参考 GitFlow + Conventional Commits + SemVer + GitHub Issues/Projects 的最佳实践。包含分支策略、提交规范、Issue 模板、PR 流程。
 category: workflow
 platforms: [windows, linux]
 related_skills:
   - git-version-control
   - github-readme-standard
   - quality-gates
   - config-unification
 triggers:
   keywords:
     - 项目管理
     - 分支策略
     - 提交规范
     - Issue
     - PR
     - 版本管理
     - 项目规划
     - 工作流
     - git flow
     - conventional commits
     - semver
     - 版本号
     - 里程碑
     - 发布流程
 ---
 
 # GitHub Project Management — 项目管理最佳实践 v1
 
 参考: GitFlow, Conventional Commits, SemVer, GitHub Community Standards
 
 ## 分支策略
 
 ### 小型项目（单人/2-3 人）
 
 ```
 master (稳定) ← feature/* (开发)
 ```
 
 ### 中型项目
 
 ```
 master (生产) ← develop (集成) ← feature/* (功能)
                                ← fix/* (修复)
                                ← docs/* (文档)
 release/* (发布候选) → master + tag
 hotfix/* (紧急修复) → master + develop
 ```
 
 ### 大型项目
 
 ```
 main (生产) ← next (预览) ← feat/* (功能)
                           ← fix/* (修复)
                           ← refactor/* (重构)
 stable/* (维护期版本分支)
 ```
 
 ## 提交规范（Conventional Commits）
 
 ```
 feat:      新功能
 fix:       bug 修复
 docs:      文档
 chore:     维护（gitignore, 构建配置）
 refactor:  重构
 test:      测试
 style:     格式
 perf:      性能
 ci:        CI/CD
 ```
 
 格式: `类型: 简短描述`
 破坏性变更: `类型!: 描述` 或 `类型(范围): 描述\n\nBREAKING CHANGE: 说明`
 
 ## 版本号（SemVer）
 
 ```
 MAJOR.MINOR.PATCH
   MAJOR: 破坏性 API 变更
   MINOR: 新增功能（向后兼容）
   PATCH: bug 修复（向后兼容）
 
 预发布: MAJOR.MINOR.PATCH-alpha/beta/rc.N
 ```
 
 ## Issue 标准
 
 ### 标签体系
 
 | 标签 | 颜色 | 说明 |
 |------|------|------|
 | bug | 红色 | 缺陷 |
 | enhancement | 蓝色 | 功能请求 |
 | documentation | 绿色 | 文档 |
 | question | 紫色 | 疑问 |
 | good first issue | 橙色 | 新手友好 |
 | help wanted | 黄色 | 需要协助 |
 | wontfix | 灰色 | 不处理 |
 
 ### Issue 模板结构
 
 ```markdown
 ### 描述
 [清晰描述问题/需求]
 
 ### 重现步骤（bug 用）
 1. 打开...
 2. 点击...
 3. 看到错误...
 
 ### 期望行为
 [应该发生什么]
 
 ### 环境
 - OS: Windows 11
 - 版本: v1.2.3
 ```
 
 ## PR 流程
 
 ```
 1. 从 master/develop 创建分支
 2. 提交变更（Conventional Commits）
 3. 创建 PR → 自动运行 CI
 4. Review + 修改
 5. 合并（Squash merge 或 Merge commit）
 6. 删除源分支
 7. 标记对应 Issue 为已关闭
 ```
 
 ## 参考来源
 
 - [GitFlow](https://nvie.com/posts/a-successful-git-branching-model/)
 - [Conventional Commits](https://www.conventionalcommits.org/)
 - [SemVer](https://semver.org/)
 - [GitHub Community Standards](https://opensource.guide/)
