---
title: 3 PR 分支硬约束 + commit 归属纪律
category: decision
tags: [discipline, commit-ownership, pr-workflow, design-principles]
created: 2026-07-03
---

# 三 PR 分支硬约束 + Commit 归属纪律

## Commit 归属纪律(用户多轮强化的硬规则)

**改哪个文件域就 checkout 到哪个 PR 分支,不在 `integration` 直接 commit**(除 test-config 一行)。

| 改的文件 | 切到分支 | 例 |
|---|---|---|
| `plugins/hermes/` 下 install-hermes.sh / adapter / guide | `pr-hermes` | `9cacc22`、`9def1c7`、`fd9130c` 都在 pr-hermes |
| `web/src/components/Perception*`、`HeroNow` | `feat/web-perception-toggles` | `e0d47c7`、`41de57e`、`bc07698` |
| `backend/miloco/.../providers/`、`omni_client.py` | `feat/web-provider-abstraction` | `15560c0`、`eb819e8`、`85154a8` |
| 跨域全栈合并测试 | `integration`(merge-only) | `60de4ed` = merge 3 PR |

## 4 大设计原则(用户反复要求)

1. **Provider 抽象 = 兼容性差异化,不替 user 设标准 envelope**
   - `request_kwargs` 只返**额外**字段(thinking、特殊 header)
   - **不**替 user 设 max_tokens/temperature/top_p/stream(这些 caller 控)
   - 反例:曾误加 `request_kwargs(self, payload, fps)` 签名让 OpenAI 返 `{"max_tokens": ...}` → user 质问"为什么加限制"→ 全部回滚(commit `eb819e8`)

2. **install-hermes.sh = 幂等 + 自动 recover**
   - 任何步骤失败 trap 提示已生效步骤 + 重跑命令
   - 退出用 EXIT trap(显式 `exit 1` 也触发),不是 ERR trap

3. **OpenClaw 风格 install-guide**
   - 不画蛇添足(不点名具体模型、不替 user 决策)
   - **删 MiniMax-M3 警告**(commit `946aa17`)

4. **provider 抽象的反 over-engineering 纪律**
   - 不要预先为未出现的 provider 留钩子
   - hardcode 走 caller,不动 provider(参见 `92283f3` 把 3 处 `"thinking":{"type":"disabled"}` 硬编码删掉迁给 provider,但 eb819e8 又把 max_tokens 之类的"伪抽象"全回滚)

## 跨引用
- 仓库身份见 [[fork-overview]]
- Mac 环境特殊性见 [[mac-dev-env]]
- 已踩坑见 [[hermes-install-pitfalls]]
