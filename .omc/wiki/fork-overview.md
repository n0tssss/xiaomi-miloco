---
title: Fork 仓库身份与拓扑
category: project-state
tags: [fork, github, pr-branches, integration]
created: 2026-07-03
---

# Xiaomi Miloco Fork — 仓库身份

## 远程
- **私有 fork**: `github.com:n0tssss/xiaomi-miloco.git`
- **上游**: `XiaoMi/xiaomi-miloco`
- **fork 克隆路径(Mac)**: `/Users/wkea/project/xiaomi-miloco`
- **fork 克隆路径(Windows,用户主开发机)**: `D:\project\xiaomi-miloco`

## 三条 PR 分支拓扑(merge-only 集成)

| 分支 | HEAD | 状态 | 实质工作 |
|---|---|---|---|
| `pr-hermes` | `9cacc22` | **PR #279 OPEN**,Zirconi review 中 | Hermes 兼容层:install-hermes.sh 全套(8 fix) + v2 backend patch 注入 + context_injection 身份/指令块剥离 + install-guide-hermes OpenClaw 风格同步 |
| `feat/web-perception-toggles` | `10d91b8` | 本地测,未提 PR | 摄像头感知 v2 矩阵开关(PerceptionDeviceTable 重构 + 测试按钮三态 + v1 backend 兜底兼容) |
| `feat/web-provider-abstraction` | `85154a8` | 本地测,未提 PR | Omni provider 抽象层(`providers/{base, openai_compatible, registry, MiniMax}.py`,MiniMax ffmpeg mux PCM→mp4) |
| `integration` | `60de4ed` | merge-only | 三条 PR 合并测试,**唯一允许直接 commit 的是 test-config 一行** |

## 改动总结文档
- `/Users/wkea/Xiaomi-Miloco-Fork-改动总结-2026-07-03.md`(本机根目录,不入仓)
- 含详细 commit 列表 + 9 条已知 bug 复盘 + 设计原则

## 跨引用
- 改 PR 分支要遵守的纪律见 [[branch-discipline]]
- Mac dev 环境特殊性见 [[mac-dev-env]]
- install-hermes.sh 已知坑见 [[hermes-install-pitfalls]]
