# miloco-hermes-plugin

Hermes Agent（[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)）的 miloco 兼容层，让装了 Hermes 的用户能像 OpenClaw 用户一样使用 miloco——出站（对话控设备/建任务）+ 入站（miloco 主动回调 agent：DYNAMIC 规则/设备欢迎/感知告警）全双向。

与 `plugins/openclaw/`（TypeScript，接入小米内部 OpenClaw 运行时）并列，互不影响。**不改动 miloco 后端代码**，后端只需改 `config.json` 把 `agent.webhook_url` 指向本兼容层提供的适配进程。

## 架构

```
                 出站（用户对话 → miloco）
用户 ──Hermes──► pre_llm_call 钩子(注入设备目录/家庭档案/身份块)
              └─► miloco-* skill ──miloco-cli──► miloco 后端 HTTP API

                 入站（miloco → 用户/agent）
miloco 后端 ──{action,payload}──► 适配进程(adapter/) ──/v1/chat/completions──► Hermes turn
                                                                       └─► miloco-notify skill ──► 推送用户
```

OpenClaw → Hermes 的映射：

| OpenClaw 概念 | Hermes 对应 | 实现 |
|---|---|---|
| 16 个 `miloco-*` skill（agentskills.io） | `~/.hermes/skills/`（同标准） | `scripts/sync-skills.py` 复制+微调 frontmatter |
| `before_prompt_build` hook（注入上下文） | `pre_llm_call` hook → `{"context": text}` | `miloco-plugin/context_injection.py` |
| `/miloco/webhook` 的 `agent` action（同步等 turn） | Hermes api_server `/v1/chat/completions`（同步，`X-Hermes-Session-Id` 头做会话连续） | `adapter/` 独立进程翻译契约 |
| `get_trace` webhook（后端反向轮询） | 同步 chat 已完成，直接回 `done` | observability 降级 |
| 3 个 tool（im_push/notify_bind/habit_suggest） | `ctx.register_tool(...)` | `miloco-plugin/tools_*.py` |
| 4 个受管 cron | `cron.jobs.create_job` + 启动时 reconcile | `miloco-plugin/cron_setup.py` |
| Service（管 backend 生命周期） | 无需 | 丢弃，backend 独立运行 |

## 目录

```
plugins/hermes/
├── miloco-plugin/        # Hermes 插件（出站核心），装到 ~/.hermes/plugins/miloco/
│   ├── plugin.yaml       # 插件清单（kind: backend, provides_tools, provides_hooks）
│   ├── __init__.py       # register(ctx)：注册 hook + 3 tool + reconcile cron
│   ├── paths.py          # $MILOCO_HOME 解析（移植 openclaw miloco/paths.ts）
│   ├── config.py         # 读 $MILOCO_HOME/config.json（移植 miloco/config.ts）
│   ├── catalog.py        # miloco-cli device catalog + 5s 节流（移植 services/catalog.ts）
│   ├── context_injection.py  # pre_llm_call 钩子，profile 分级装配上下文（移植 hooks/prompt.ts）
│   ├── tools_notify.py   # miloco_im_push / miloco_notify_bind（移植 tools/notify.ts）
│   ├── notify_target.py  # 通知目标解析
│   ├── tools_habit.py    # miloco_habit_suggest 状态机（移植 home-profile/suggestions.ts）
│   └── cron_setup.py     # 4 个受管 cron reconcile（移植 home-profile/scheduler.ts）
├── adapter/              # 入站适配进程，把 miloco webhook 翻译成 Hermes turn
│   ├── __main__.py       # 入口：python -m plugins.hermes.adapter
│   ├── server.py         # aiohttp: POST /miloco/webhook {action,payload} → {code,data}
│   ├── hermes_client.py  # 调 Hermes api_server /v1/chat/completions（同步，X-Hermes-Session-Id 会话连续）
│   └── session_map.py    # (sessionKey, lane) → Hermes session_id 确定性映射
├── scripts/
│   ├── sync-skills.py    # 把 plugins/skills/miloco-* 同步到 skills/，删 openclaw.requires
│   └── install.sh        # 一键安装到 ~/.hermes/
├── skills/               # sync-skills.py 生成的 16 个 miloco-* skill（gitignore）
└── tests/                # 单测
```

## 安装

### 快速安装（一键，推荐）

前置：已装 Hermes Agent（`~/.hermes` 存在）、miloco 后端 + `miloco-cli` 在 PATH。

```bash
bash plugins/hermes/install-hermes.sh
```

这一行会做完 7 件事：

1. 前置检查（hermes / miloco-cli / python / `$MILOCO_HOME`）
2. 同步 16 个 skill 到 `~/.hermes/skills/`
3. 复制插件到 `~/.hermes/plugins/miloco/miloco-plugin/`
4. 复制 adapter 到 `~/.hermes/plugins/miloco/adapter/`
5. **自动 patch** `$MILOCO_HOME/config.json` 的 `agent` 段（备份 `config.json.bak-<ts>`）
6. **自动**给 `~/.hermes/.env` 补 `API_SERVER_KEY`（如缺失则生成，存在则复用）
7. **自动 nohup 启** adapter，PID 写到 `~/.hermes/miloco-adapter.pid`，日志到 `~/.hermes/miloco-adapter.log`

**后续你只要做一件事**：

```bash
hermes gateway restart   # 让插件和新 API_SERVER_KEY 生效
hermes chat -q "把客厅灯打开" -Q   # 试一下
```

脚本**幂等**，重跑不会破坏现有配置，会保留同一 Bearer 重启 adapter。

### adapter 生命周期

```bash
bash plugins/hermes/scripts/miloco-adapter.sh start    # 启
bash plugins/hermes/scripts/miloco-adapter.sh stop     # 停
bash plugins/hermes/scripts/miloco-adapter.sh restart  # 重启
bash plugins/hermes/scripts/miloco-adapter.sh status   # PID / 端口 / 健康
bash plugins/hermes/scripts/miloco-adapter.sh logs     # tail -f 日志
bash plugins/hermes/scripts/miloco-adapter.sh env      # 显当前 .env 里的环境变量
```

> adapter 默认端口 18789，与 OpenClaw 默认 webhook 端口一致，使 miloco 默认 `agent.webhook_url` 尽量不用改。

### 手动 / 高级安装

`scripts/install.sh` 保留给想自己一步步做的用户：只复制 skill 和插件，**不** patch miloco config.json、**不**补 .env、**不**启 adapter。装完按下面"关键配置"自己填 3 段。

### 关键配置（手动安装参考）

**miloco 后端** `$MILOCO_HOME/config.json` 的 `agent` 段：
```json
"agent": {
  "webhook_url": "http://127.0.0.1:18789/miloco/webhook",
  "auth_bearer": "<随机串，需与 adapter 的 ADAPTER_AUTH_BEARER 一致>"
}
```

**Hermes** `~/.hermes/.env`：启用 api_server 平台并设 `API_SERVER_KEY=<密钥>`。

**适配进程**：
```bash
ADAPTER_AUTH_BEARER=<同 agent.auth_bearer> \
HERMES_API_URL=http://127.0.0.1:8642 \
HERMES_API_KEY=<同 API_SERVER_KEY> \
ADAPTER_PORT=18789 \
python -m plugins.hermes.adapter
```

> 推荐用 `bash scripts/miloco-adapter.sh start` 替代直接 nohup，自带 PID/日志/健康检查。

## 与 OpenClaw 版的差异（已知降级）

1. **context 注入位置**：Hermes `pre_llm_call` 只能往 **user message** 注入 `{"context": text}`（为保 prompt cache，不污染 system prompt）。OpenClaw 的 `before_prompt_build` 是往 system prompt 追加。功能等价，但注入位置不同。
2. **observability 降级**：`get_trace` 在 Hermes 下直接回 `done`，不回传 turn 元数据，故 miloco 后端的 `agent_runs` 端到端追踪链路不完整。
3. **上下文溢出自愈**：Hermes api_server 无 session 删除/重置路由，识别溢出错误文案后丢弃会话上下文、用无 `X-Hermes-Session-Id` 的全新 turn 重试一次（近似 OpenClaw 的 `deleteSession + re-run`，但丢掉该会话此前记忆）；溢出信号靠错误文案匹配，识别范围偏宽。
4. **通知投递**：`miloco_im_push` 经 Hermes 内置 `send_message` tool 投递；未绑定通知目标时不 fallback 到「最近活跃 channel」（Hermes SessionDB 无 OpenClaw 的 lastTo/lastChannel 结构），而是返回 `needsBind:true` 引导用户先 `miloco_notify_bind`。

以上 3、4 项依赖 Hermes 实例实测，已标 best-effort。

## 验证

```bash
# 单测
pytest plugins/hermes/tests/

# 出站冒烟（需 Hermes 已启动 + 插件已装）
hermes chat -q "把客厅灯打开" -Q   # -Q 非交互静默模式

# 确认 cron
hermes cron list   # 应见 4 个 [miloco:home-profile] 任务
```

### 已实测验证（Hermes v0.10.0 + GLM via bigmodel OpenAI 端点）
- 出站：插件加载（`hermes plugins list` 显示 enabled）、16 skill 可用、`pre_llm_call` 钩子触发注入设备目录/家庭档案、4 个受管 cron 注册并按计划触发、`miloco-devices` skill 被 agent 正确调用并执行 `miloco-cli`（缺 miloco-cli 时优雅降级）。
- 入站：miloco `{action:"agent",payload}` → 适配器 → Hermes `/v1/chat/completions` 同步 turn → `{code:0,data:{runId,status:"ok"}}`；幂等/`get_trace`/未知 action/鉴权失败 各分支均符合契约。
- 待用户环境补齐：miloco 后端 + 小米账号（真实设备控制链路 `skill → miloco-cli → 后端 → 设备`，此链路与 OpenClaw 版完全相同）。

### Hermes 侧需注意
- **croniter**：Hermes v0.10.0 的 cron 调度需 `pip install croniter`（管理 cron 表达式），否则 4 个受管任务创建失败。
- **api_server 启用**：`~/.hermes/.env` 设 `API_SERVER_KEY=<密钥>` 即自动启用 api_server 平台（默认端口 8642），适配器据此驱动 turn。
- **模型**：Hermes 的 `custom` provider 对非 openai.com 域名按 host 推导 env（如 bigmodel → `BIGMODEL_API_KEY`），或在 `config.yaml` 的 `model.api_key` 直接写 key 最稳。

详见 `knowledge/03-features/hermes-integration.md`。
