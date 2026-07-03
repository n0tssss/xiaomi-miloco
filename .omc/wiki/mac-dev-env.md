---
title: Mac dev 环境(M1)特殊性
category: environment
tags: [macos, arm64, dev-env, hermes-local, miloco-cli]
created: 2026-07-03
---

# Mac Dev 环境(M1)特殊性

## 系统信息
- **平台**: darwin / arm64(M1 Mac)
- **Python 系统**: 3.9.6(`/usr/bin/python3`)
- **Hermes Agent Python**: 3.11.15(在 `~/.hermes/...` venv)
- **Hermes Agent 版本**: v0.17.0 (2026.6.19) · upstream 7c1a0295
- **uv**: `/Users/wkea/.local/bin/uv` 已装,tools 目录:`~/.local/share/uv/tools/`

## 已装 vs 未装

| 组件 | 状态 | 位置 |
|---|---|---|
| Hermes Agent | ✓ | `~/.hermes/`,CLI `~/.local/bin/hermes` |
| miloco-cli | ✗ | 不在 PATH(没装 backend) |
| `~/.openclaw/miloco/` | ✗ | 不存在(没装 backend) |
| `~/.hermes/plugins/miloco/` | ✗ | 不存在(没装 plugin) |
| `~/.local/share/uv/tools/supervisor` | ✓ | 仅 supervisor(不是 miloco) |
| 16 个 miloco-* skill | ✗ | 没 sync |
| `MILOCO_HOME` env | ✗ | 未 export |

## Mac vs Windows 关键差异

- **主开发机是 Windows**:`D:\project\xiaomi-miloco`,有 `CLAUDE.md` + `.claude/branch-rules.md` + `MEMORY.md` 索引
- **Mac 是测试机**:用 fork 仓库做 install-hermes.sh 端到端验证
- 脚本有跨平台适配(`netstat` 优先,`lsof`/`ss` 兜底;`taskkill` 优先,`kill -9` 兜底)
- **bash 3.2 兼容性**:macOS 自带 bash 3.2,heredoc 内嵌大段 Python + (fallback) 等括号会解析挂 → install-hermes.sh 把 IM 探测挪到外部 Python 脚本(commit `f984c98`)
- **launchd 优先**:`Darwin && launchctl` 走 LaunchAgent plist,adapter 脱离 install.sh 进程组,exit 1 不会 SIGHUP 误杀

## 默认路径(Mac)
- `HERMES_HOME` = `~/.hermes`
- `MILOCO_HOME` = `~/.openclaw/miloco`
- `ADAPTER_PORT` = 18789
- adapter PID = `~/.hermes/miloco-adapter.pid`
- adapter log = `~/.hermes/miloco-adapter.log`

## 装后端标准命令
上游 release 装 backend(本机 release route):
```bash
curl -LsSf https://github.com/XiaoMi/xiaomi-miloco/releases/latest/download/install.sh | bash -s -- --agent-prepare
```
(用户 fork 的 plugin 自己通过 install-hermes.sh 装,backend 复用上游 release)

## 跨引用
- 仓库身份见 [[fork-overview]]
- 分支纪律见 [[branch-discipline]]
- 装过程中的坑见 [[hermes-install-pitfalls]]
