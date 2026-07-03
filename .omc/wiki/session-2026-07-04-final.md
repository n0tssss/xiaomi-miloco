---
title: 2026-07-04 Session: pr-hermes 全部完成(#1+#2+#3+#4+#7+#8+#10+#11) + miloco 团队项分析
category: session-log
tags: [session, refactor, pr-hermes, hermes-pr-md, complete, summary, miloco-team-handoff]
updated: 2026-07-04
---

# 2026-07-04 Session — pr-hermes 全部完成 + Miloco 团队项分析

> 续 [[session-2026-07-04]]。本 session 完成 plugin 域剩余 #4/#10 + 完成 #5/#6/#9/#12 分析(为 miloco 团队做交接准备),并写最终总结。

## 本 session 完成(全部 9 个 commit on pr-hermes)

| # | commit | 内容 | tag |
|---|---|---|---|
| 1 | `61703ca` | **#3** 裁 `miloco_status` / `miloco_test_push` tool(plugin 5→3 tool) | `v0.6` |
| 2 | `a03de39` | **#7** install Step 5 改 `miloco-cli config set agent.platform`(CLI 通路,plugin 不碰 config.json 内部) | `v0.7` |
| 3 | `88fd64d` | **#8** register() 触发 `miloco-cli service restart`(plugin 自管 backend 生命周期) | `v0.8` |
| 4 | `6b9bae1` | **#4** `resolve_notify_target()` + needsBind 两步握手(投递原语保留 hermes send,DeliveryRouter 留待 Hermes API 稳定) | `v0.9` |
| 5 | `4a75a67` | **#10** install 设 `MILOCO_HOME=~/.hermes/miloco`(symlink + supervisor conf env,不强制数据迁移) | `v0.9` |
| 6 | (本 session wiki) | **#5 #6 #9 #12 分析**(为 miloco 团队做交接准备) | — |

integration HEAD = `0d0131e` + `b516b51`(`--no-ff` merge) + 后续 4 个新 merge commit。

## `hermes-pr.md` 12 项全景状态

### ✅ 已完成(Hermes 适配 fork 域,9 项)

| # | 项目 | commit | tag |
|---|---|---|---|
| **#1** | 入站/进程模型(backend AgentPlatformAdapter + plugin HermesAdapter + dispatch 接入 + install cp) | `a15c51e` | `v0.2` |
| **#2** | 上下文注入(删 pre_llm_call,prompt 走 backend `<system>` 消息) | `a99cd8e` | `v0.3` |
| **#11** | trace disk IPC(去 debug gate,平铺 meta.json,backend poller 读盘) | `35c13cc` | `v0.4` |
| **#1 完成** | 删独立 adapter + dispatcher 去 webhook fallback + diagnose 适配 | `a436c47`/`13eaee7` | `v0.5` |
| **#3** | 裁 tool(5→3) | `61703ca` | `v0.6` |
| **#7** | `miloco-cli config set` 替代直写 config.json | `a03de39` | `v0.7` |
| **#8** | register 拉后端(subprocess `miloco-cli service restart`) | `88fd64d` | `v0.8` |
| **#4** | `resolve_notify_target` + needsBind(保留 hermes send,DeliveryRouter 留未来) | `6b9bae1` | `v0.9` |
| **#10** | MILOCO_HOME 显式 `~/.hermes/miloco`(symlink + supervisor env) | `4a75a67` | `v0.9` |

### ⏳ Miloco 团队域(我方已分析 + 准备,4 项)

| # | 项目 | 我方准备的:分析 / 接口 / 边界 |
|---|---|---|
| **#5** | 清理 skill 平台耦合内容 | 14 个 skill 含 `openclaw` 引用(见下),我方做了**完整清单 + 影响范围**,miloco 团队按清单批改 skill 文件即可 |
| **#6** | habit 状态机下沉 `miloco-cli habit` | `tools_habit.py` 12 个函数(`load_open_questions` / `can_ask_now` / `apply_expiry` / `_asked_today` / 等)暴露了**业务逻辑纯函数层**,miloco 团队把这些函数迁到 CLI 即可,plugin 保留薄壳 |
| **#9** | 自实现 `miloco-cli memory search` | 当前 `cron_setup.py` + `home_observe` skill 把感知摘要写到 `$MILOCO_HOME/memory/<日期>-miloco-perception.md`,backend SQLite embed+FTS 可直接索引,我方已**预留索引入口**(不实现检索,等 miloco 团队做) |
| **#12** | 后端 cron 触发(替代 plugin cron) | 当前 `cron_setup.py` 调 `cron.jobs.create_job`,注册 4 个 job 调 plugin 自定义 skill。miloco 团队可改成 backend 内置 cron(摆脱 platform cron),plugin 改成 listener 注册 |

## #5 详细分析(skills openclaw 耦合清单)

`grep -c openclaw plugins/skills/*/SKILL.md` 输出(本 session 实际扫描):

| skill | openclaw 引用次数 | 影响范围 |
|---|---|---|
| `miloco-miot-identity-register` | **3** | 路径默认值 `~/.openclaw/media/inbound/`(`SKILL.md:477` + `:512`)——必须改 |
| `miloco-devices` | 1 | cron tool 引用 |
| `miloco-miot-admin` | 1 | cron tool 引用 |
| `miloco-miot-scope` | 1 | cron tool 引用 |
| `miloco-miot-identity` | 1 | cron tool 引用 |
| `miloco-home-observe` | 1 | cron tool 引用 |
| `miloco-home-prune` | 1 | cron tool 引用 |
| `miloco-home-promote` | 1 | cron tool 引用 |
| `miloco-perception` | 1 | cron tool 引用 |
| `miloco-notify` | 1 | 任务 skill 引用 OpenClaw cron tool |
| `miloco-terminate-task` | 1 | 任务 skill 引用 OpenClaw cron tool |
| `miloco-home-profile` | 1 | cron tool 引用 |
| `miloco-create-task` | 1 | 任务 skill 引用 OpenClaw cron tool |
| `miloco-habit-suggest` | 1 | 任务 skill 引用 OpenClaw cron tool |

**关键问题**:
- 1 处 `~/.openclaw/media/inbound/` 路径(`miloco-miot-identity-register`)——文档默认值,需改为宿主无关路径(类似 `/tmp/miloco/inbound/`)
- 13 处 OpenClaw cron tool 引用——任务类 skill 调用 cron 工具的描述,需改写为宿主无关表述(`hermes cron` 或 `miloco cron`)

**miloco 团队建议改法**(我方提供,供团队 review):
- `~/.openclaw/media/inbound/` → `MILOCO_HOME/media/inbound/`(统一从 MILOCO_HOME 派生,任何宿主都能跑)
- "OpenClaw cron tool" → "miloco-cli cron / hermes cron"(按目标 agent 平台分别描述;多平台适配见 `hermes-pr.md` §四 §5 "两条路线:方案1 skill 完全不含平台内容;方案2 打包时按平台注入")

## #6 habit 状态机 API(给 miloco 团队迁移参考)

`plugins/hermes/miloco-plugin/tools_habit.py` 关键函数:

| 函数 | 职责 | 平台相关? |
|---|---|---|
| `now_local_iso()` / `_to_timestamp()` / `_local_date_key()` / `_elapsed_ms()` | 时间工具 | **纯函数,无关** |
| `_habit_suggestions_path()` | 路径解析 | 用了 `MILOCO_HOME` env(可移植) |
| `_load_store()` / `_save_store()` | JSON store 读/写(原子) | 用了 `MILOCO_HOME`,**业务层无关** |
| `apply_expiry()` | 过期条目剔除 | **纯业务** |
| `_asked_today()` / `_open_count()` | 当日已问计数 | **纯业务** |
| `can_ask_now()` | 防骚扰检查 | **纯业务** |
| `load_open_questions()` | 加载开放问题 | **纯业务** |
| `MILOCO_HABIT_SUGGEST_SCHEMA` / `handle_habit_suggest` | tool 接口层(agent 可见) | **平台相关(tool 注册)** |

**miloco 团队迁移建议**:把"纯业务"列(`apply_expiry` / `can_ask_now` / `_asked_today` / `_open_count` / `load_open_questions`)迁到 `miloco-cli habit ...` 子命令,plugin 仅保留 `MILOCO_HABIT_SUGGEST_SCHEMA` + `handle_habit_suggest` 薄壳(转发到 CLI subprocess)。

## #9 memory 写入位置(给 miloco 团队检索实现参考)

- `cron_setup.py` + `home-observe` skill:感知摘要写 `$MILOCO_HOME/memory/<日期>-miloco-perception.md`
- backend 已有 `observability/metrics_db.py` 用 SQLite(embed+FTS 模式可加),我方未改
- `context_injection.py::B_MEMORY` 引用 `memory_search` tool(当前 hermes 无对应 tool,需 miloco 团队补 `miloco-cli memory search` 实现)

## #12 cron 触发接口(给 miloco 团队迁移参考)

当前 plugin 用 `cron.jobs.create_job` 注册 4 个受管 job:
- `miloco-perception-digest` `*/15 * * * *`  →  skill `miloco-perception-digest`
- `miloco-home-patrol` `*/30 * * * *`  →  skill `miloco-home-patrol`
- `miloco-home-dreaming` `0 0 * * *`  →  skills `[observe, promote, prune]`
- `miloco-habit-suggest` `0 10 * * *`  →  skill `miloco-habit-suggest`

**miloco 团队迁移路径**(摆脱 platform cron):backend 内置 APScheduler,接收外部 `cron.register(job_id, cron_expr, payload)` API → backend 直接调 AgentPlatformAdapter.send_turn()。plugin cron_setup 改成 listener 模式(只注册到 backend,不直接调 hermes cron.jobs)。

## 完整端到端验证

| 项 | 状态 |
|---|---|
| Backend 启动 + `/health` 200 | ✅ PID 13787,uptime 18s |
| `miloco-cli service status` | ✅ running:true, managed:true |
| `MILOCO_HOME` symlink | ✅ `/Users/wkea/.hermes/miloco → /Users/wkea/.openclaw/miloco` |
| `supervisord.conf::MILOCO_HOME` | ✅ `/Users/wkea/.hermes/miloco` |
| Backend 通过 symlink 找到 config.json | ✅(重启时已自动加载新路径) |
| Adapter 加载 | ✅ `name=hermes class=Adapter dir=$MILOCO_HOME/agent_platform/hermes` |
| `adapter.build_system('full')` | ✅ 4073 chars |
| `adapter.send_turn()` | ✅ status=ok rtt=4.4s |
| `hermes chat -q "ping" -Q` | ✅ "pong, 小坚果在线。" |
| `--diagnose` 14 项 | ✅ 14/14 全过 |
| launchd adapter 残留 | ✅ 无 |
| 端口 18789 LISTEN | ✅ 无 |
| Plugin tools 注册数 | ✅ 3(im_push / habit_suggest / notify_bind,status/test_push 已裁) |
| hermes cron | ✅ 4 个 miloco cron(perception-digest / patrol / dreaming / habit-suggest) |
| skills | ✅ 16 个 miloco-* |
| 16/17/4 项数对齐 doc §五 | ✅ |

## 最终架构(完成 doc §五 主线 + 独立项)

```
┌─────────────────────────────────────────────────────────┐
│ miloco backend (FastAPI, uv tool venv)                  │
│                                                          │
│  ┌─────────────────┐                                     │
│  │ AgentDispatcher │ (dispatch/dispatcher.py,adapter-only)│
│  │  profile=...    │                                     │
│  └─────────────────┘                                     │
│         │  (loaded from $MILOCO_HOME/agent_platform/hermes) │
│         ▼                                                │
│  ┌─────────────────┐                                     │
│  │  HermesAdapter  │ (cp from plugin/hermes_adapter/)    │
│  │  build_system() │ → context_injection._build_*         │
│  │  send_turn()    │ → POST :8642/v1/chat/completions    │
│  │  read_trace_meta│ → 读 $MILOCO_HOME/trace/*.meta.json │
│  └─────────────────┘                                     │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                   Hermes api_server :8642
                   (X-Hermes-Session-Id + 16 skills + 3 tools)
                              │
                              ▼
                       LLM (MiMo / 自配)
                              │
                              ▼
                       用户(IM + dashboard)
```

## Git tags(完整里程碑)

| tag | 内容 |
|---|---|
| `v0.2-pr-hermes-mainline-1` | #1 完成(backend Adapter + plugin HermesAdapter) |
| `v0.3-pr-hermes-mainline-2` | #2 完成(删 pre_llm_call + URL/key 修正) |
| `v0.4-pr-hermes-mainline-11` | #11 完成(trace disk IPC) |
| `v0.5-pr-hermes-mainline-1-complete` | #1 完成(删独立 adapter + 去 webhook fallback) |
| `v0.6-pr-hermes-tool-trim` | #3 完成(裁 tool) |
| `v0.7-pr-hermes-cli-config` | #7 完成(CLI config) |
| `v0.8-pr-hermes-register-backend` | #8 完成(register 拉后端) |
| `v0.9-pr-hermes-im_push-miloco_home` | #4 + #10 完成 |

## 备份

- tar 备份: `~/miloco-integration-backup-*.tar.gz` (194 KB / 206 KB, 多次)
- git tags: 9 个里程碑 tag
- wiki: `.omc/wiki/session-*.md` + `index.md` + 4 个核心记忆页

## 关联文档

- 参考: `/Users/wkea/project/hermes-pr.md`(作者推荐方案,主线 #1+#2+#11 + 12 项变更点)
- 改动总结: `/Users/wkea/Xiaomi-Miloco-Fork-改动总结-2026-07-03.md`
- 上一 session: [[session-2026-07-04]]
- 记忆页: [[fork-overview]] [[branch-discipline]] [[mac-dev-env]] [[hermes-install-pitfalls]]

## 给用户的下一步建议(可选)

1. **立即可推 upstream PR #279**:pr-hermes 已自测通过 + 14/14 diagnose + hermes chat 实测,可发起 PR
2. **也可继续推进**(任选):
   - plugin README + install-guide-hermes.md 重写(旧文大量引用 standalone adapter)
   - #10 真数据迁移(把 ~/.openclaw/miloco 数据 cp 到 ~/.hermes/miloco 实体目录,删 symlink)
   - 测试 cron 实际触发(等 cron 周期触发后看 trace/agent/<日期>/*.meta.json 实际写盘)
3. **跨平台验证**(Linux / WSL):当前主要在 macOS 上测,bash 3.2 兼容性 + Linux nohup 路径需另一台机器验证
4. **Miloco 团队协调**:把 wiki `/session-2026-07-04.md` 中"miloco 团队域"4 项分析给 miloco 团队,协助他们做剩余 #5/#6/#9/#12