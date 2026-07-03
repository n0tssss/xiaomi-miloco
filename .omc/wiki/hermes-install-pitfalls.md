---
title: install-hermes.sh 流程与已知坑
category: debugging
tags: [install-hermes, pitfalls, fixed-bugs, pr-hermes, hermes-agent]
created: 2026-07-03
---

# install-hermes.sh 流程与已知坑

## 9 步流程(完整安装)

| Step | 内容 | 关键修复 commit |
|---|---|---|
| 1 | 前置检查(python/miloco-cli/Hermes/config.json) | + 半装残留检测 + MILOCO_HOME 持久化 + python_bin auto-fix(`bb70c59`) |
| 1.5 | 自动 service start 后端(atexit 兜底) | jq 解析 running 字段,无 jq 时严格 grep `d85cebc` |
| 2 | 拿/复用 adapter Bearer(.env 已有则复用,否则 secrets 生成) | — |
| 3 | sync 16 个 skill → `~/.hermes/skills/` | — |
| 4 | 复制 plugin + adapter 到 `~/.hermes/plugins/miloco/`,预编译 pyc | — |
| 4.5 | 探测 Hermes 已配 IM 平台 → 写 state.json::deliver.target | 挪到外部 Python 脚本 `f984c98`(bash 3.2 heredoc 嵌套括号挂) |
| 4.6 | 升级保留旧 deliver.target(除非 `--reset-deliver`) | — |
| 4.7 | **同步本地 ONNX 模型** → `~/.openclaw/miloco/models/` + 写 `config.json::models` | `e8b40d5` 加(对齐 upstream install.sh --agent-finish) |
| 5 | patch `${MILOCO_HOME}/config.json::agent.{webhook_url,auth_bearer}`,备份 | — |
| 6 | 写 `~/.hermes/.env::API_SERVER_KEY`(仅缺失时追加) | — |
| 7 | 启 adapter:macOS launchd / 其他 nohup | — |
| 8 | `hermes plugins enable miloco` | 严格匹配 `│ enabled │` 列(防 `not enabled` 假阳性 `558b589`) |
| 8.5 | 兜底清 `~/.hermes/config.yaml::plugins.disabled` 里 miloco* 残留(nested plugin key 不被 hermes enable 清) | — |
| 9 | 记录 hermes/miloco-cli/plugin/git_commit 版本到 state.json | — |

## 终态必须由用户自己跑
- **`hermes gateway restart`**(Herme anti-restart-loop 不让 agent 在 gateway 进程内重启)
- 或 `hermes gateway stop && hermes gateway start`

## 9 条已修 bug 复盘

| 现象 | 根因 | commit |
|---|---|---|
| 前端永远加载旧 dist | 上次 commit dist 时 build 出旧版 JS | `447100f` 重建 |
| Step 1.9 永远 silent skip | system python3 import miloco 失败 | `fd9130c` 改用 uv tool python |
| 单独关视频/音频预览消失 | HeroNow 用 `c.connected` 过滤 | `bc07698` 改 `c.inUse` |
| 422 on bulk master | v1 router 不认 video_enabled/audio_enabled | `e0d47c7` 前端补 inUse |
| 全部显示 OFF | listCameras 不兜底 v1 缺字段 | `e0d47c7` `?? in_use` |
| 测试弹框空且无错误 | `Promise.all` 失败只 toast,错误消失 | `10d91b8` 顺序 catch + 弹框内显示 |
| Step 1.10 永远 silent skip | FORK_SRC 路径算错(`../../` 走错层) | `9cacc22` 改两次 dirname |
| PR 评审旧身份 prompt 污染 | linter 自动 revert 修复 | `071931f` + `CLAUDE.md` 防再犯 |
| bash 3.2 heredoc 解析挂 | 内嵌 Python + (fallback) 嵌套括号 | `f984c98` 挪到外部脚本 |

## --diagnose 模式(12 项,无修改)
1. python 可用
2. python 依赖(aiohttp/httpx/croniter)
3. miloco-cli 在 PATH
4. miloco backend 在跑
5. Hermes 目录存在
6. miloco config.json::agent.webhook_url
7. Hermes .env::API_SERVER_KEY(恰好 1 行)
8. plugin 已装到 `~/.hermes/plugins/miloco/`
9. plugin enabled(严格 `│ enabled │`)
10. adapter 进程(macOS launchd / 端口 18789)
11. adapter /health(200)
12. state.json::deliver.target(非 null)
13. 16 个 miloco-* skill
14. 4 个受管 cron job(`hermes cron list` 含 miloco)

## 常见修复
- 半装残留:重跑 `bash plugins/hermes/install-hermes.sh`(幂等,自动 recover)
- backend 没起:`miloco-cli service start`(装完 atexit 杀的)
- python_bin 找不到 miloco:Step 1.8 自动扫 uv/pyenv venv 修
- `│ not enabled │` 假阳性:Step 8 严格匹配 `│ enabled │`
- upstream hermes 漏清 nested plugin key:Step 8.5 兜底

## 跨引用
- 仓库身份见 [[fork-overview]]
- 分支纪律见 [[branch-discipline]]
- Mac 环境特殊性见 [[mac-dev-env]]
