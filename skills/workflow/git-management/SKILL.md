---
name: git-management
description: GitHub 仓库管理 — 合并版本管理 + 项目管理。包含分支策略、提交规范、Issue/PR 管理、SemVer 版本号、README 标准、定时同步。
category: workflow
platforms: [windows, linux]
related_skills:
  - quality-gates
  - data-security-audit
triggers:
  keywords:
    - 版本管理
    - GitHub
    - git
    - 备份
    - 同步
    - 项目管理
    - 分支
    - 提交
    - PR
    - 仓库管理
    - 发布
---

# Git Management — GitHub 仓库管理 v1

## 分支策略

单人: master ← feature/*
多人: master ← develop ← feature/* / fix/* / docs/*

## 提交规范 (Conventional Commits)

feat: / fix: / docs: / chore: / refactor: / test: / style: / perf:

## 版本号

SemVer: MAJOR.MINOR.PATCH

## 同步规则

- 定时: git add -u（仅已跟踪文件）
- 手动: git add <specific path>
- 推送前: data-security-audit 检查
