# miloco × Hermes Agent — 双向兼容层

让装了 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的用户能像 OpenClaw 用户一样使用 miloco：出站（对话控设备/建任务）+ 入站（miloco 主动回调 agent：DYNAMIC 规则/设备欢迎/感知告警）全双向。与 `plugins/openclaw/` 并列，互不影响。**不改动 miloco 后端代码**。

> 📌 **把本文档发给你的 AI agent（Claude / Hermes / Codex / ...）即可让它自动完成安装**。见底部「[给 AI agent 的安装 Prompt](#给-ai-agent-的安装-prompt)」。

---

## 一键安装

```bash
bash plugins/hermes/install-hermes.sh
```

这一行会做完 7 件事：前置检查 → 同步 16 个 skill → 复制插件 + adapter → patch miloco `config.json`（备份）→ 写 `~/.hermes/.env` 的 `API_SERVER_KEY` → nohup 启 adapter → 打印终态。**幂等**，重跑保留 Bearer 重启进程。

装完你只要做一件事：

```bash
hermes gateway restart
```

---

## If you're an AI agent 🤖

**Goal**: 在本机装好 miloco × Hermes 兼容层，让 hermes gateway 重启后能用 miloco-* skill，并通过 adapter 接收 miloco 后端回调。

**Prerequisites**（缺任何一项会 exit 1，明确报错）：

- `~/.hermes` 已存在（`hermes` CLI 在 PATH）
- `miloco-cli` 在 PATH（来自 miloco 后端安装）
- `python3` 或 `python` 在 PATH
- `$MILOCO_HOME/config.json` 存在（默认 `~/.openclaw/miloco/config.json`）

**执行步骤**：

```bash
# 1. 跑一键安装
cd <repo_root>  # xiaomi-miloco 仓库根目录
bash plugins/hermes/install-hermes.sh
# 预期输出末尾："✅ 安装完成（可重复执行，幂等）" + PID + 日志路径

# 2. 校验 7 步全过（推荐，让 agent 确认环境真没问题）
bash plugins/hermes/tests/test_install_e2e.sh
# 预期输出末尾："PASS: 22, FAIL: 0" + "全部通过 ✓"

# 3. 重启 hermes gateway 让插件和新 API_SERVER_KEY 生效
hermes gateway restart
# 或：hermes gateway stop && hermes gateway start

# 4. 验证插件加载
hermes plugins list
# 预期：看到 "miloco" 状态 enabled

# 5. 验证 skill 可用
ls ~/.hermes/skills/miloco-*
# 预期：16 个目录（miloco-devices, miloco-perception, miloco-notify, ...）

# 6. 验证 adapter 进程在跑
bash plugins/hermes/scripts/miloco-adapter.sh status
# 预期：adapter 在跑，端口 PID=xxxxx，health OK
```

**装完回报给用户**（按以下格式）：

```
✅ miloco × Hermes 兼容层已装好
  - 插件: ~/.hermes/plugins/miloco/miloco-plugin (enabled)
  - 16 个 skill: ~/.hermes/skills/miloco-*
  - adapter: PID=<pid>，端口 18789，日志 ~/.hermes/miloco-adapter.log
  - miloco config.json: webhook_url + auth_bearer 已 patch，备份 config.json.bak-<ts>
  - Hermes .env: API_SERVER_KEY 已追加

后续你试一下：
  hermes chat -q "把客厅灯打开" -Q     # 出站试
  miloco-cli device list              # 出站试（不带 hermes）
  # 真实设备控制链路需要你的 miloco 后端 + 小米账号，链路是
  # skill → miloco-cli → miloco 后端 → 小米设备，与 OpenClaw 版完全相同
```

### Troubleshooting（如果步骤失败）

| 现象 | 解决 |
|---|---|
| `找不到 miloco-cli` | 装 miloco 后端：`curl -LsSf https://github.com/XiaoMi/xiaomi-miloco/releases/latest/download/install.sh \| bash` |
| `找不到 Hermes 目录` | 装 Hermes：`curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` |
| `找不到 config.json` | 设 `export MILOCO_HOME=/path/to/your/miloco/home` |
| `adapter 启动失败，端口 X 未监听` | 端口被占：`lsof -iTCP:X -sTCP:LISTEN`（或 `netstat -ano \| grep X`）找占用者 kill；或设 `export ADAPTER_PORT=18790` 换端口 |
| `No module named aiohttp` | adapter 依赖：`pip install aiohttp httpx` |
| `No module named croniter` | Hermes v0.10.0 cron 调度依赖：`pip install croniter` |
| `hermes cron list` 没看到 4 个 miloco 任务 | `pip install croniter`，然后 `hermes gateway restart` |
| `hermes chat` 报 401 / API key 问题 | 检查 `~/.hermes/config.yaml` 的 `model.api_key` 或对应 provider 的 env，详见下方「Hermes 侧需注意」 |
| 装完发现 adapter 没在跑 | `bash plugins/hermes/scripts/miloco-adapter.sh logs` 看日志；`status` 看 PID/端口/健康 |

### 失败时如何回滚

```bash
# 1. 停 adapter
bash plugins/hermes/scripts/miloco-adapter.sh stop

# 2. 卸插件 + skill
rm -rf ~/.hermes/plugins/miloco
rm -rf ~/.hermes/skills/miloco-*

# 3. 还原 miloco config.json（patch 前的备份）
ls $MILOCO_HOME/config.json.bak-*
cp $MILOCO_HOME/config.json.bak-<ts> $MILOCO_HOME/config.json

# 4. 去掉 .env 里追加的 API_SERVER_KEY
#    编辑 ~/.hermes/.env，删掉最后一行 API_SERVER_KEY=...

# 5. 重启 hermes
hermes gateway restart
```

---

## adapter 生命周期

```bash
bash plugins/hermes/scripts/miloco-adapter.sh start    # 启
bash plugins/hermes/scripts/miloco-adapter.sh stop     # 停
bash plugins/hermes/scripts/miloco-adapter.sh restart  # 重启
bash plugins/hermes/scripts/miloco-adapter.sh status   # PID / 端口 / 健康
bash plugins/hermes/scripts/miloco-adapter.sh logs     # tail -f 日志
bash plugins/hermes/scripts/miloco-adapter.sh env      # 显当前 .env 里的环境变量
```

> adapter 默认端口 18789，与 OpenClaw 默认 webhook 端口一致，使 miloco 默认 `agent.webhook_url` 尽量不用改。

---

## 架构

```
                 出站（用户对话 → miloco）
用户 ──Hermes──► pre_llm_call 钩子(注入设备目录/家庭档案/身份块)
              └─► miloco-* skill ──miloco-cli──► miloco 后端 HTTP API

                 入站（miloco → 用户/agent）
miloco 后端 ──{action,payload}──► 适配进程(adapter/) ──/v1/chat/completions──► Hermes turn
                                                                       └─► miloco-notify skill ──► 推送用户
```

OpenClaw → Hermes 映射：

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
├── install-hermes.sh        # 一键安装（patch + 启 adapter，幂等）
├── miloco-plugin/           # Hermes 插件（出站核心），装到 ~/.hermes/plugins/miloco/
│   ├── plugin.yaml          # 插件清单（kind: backend, provides_tools, provides_hooks）
│   ├── __init__.py          # register(ctx)：注册 hook + 3 tool + reconcile cron
│   ├── paths.py             # $MILOCO_HOME 解析
│   ├── config.py            # 读 $MILOCO_HOME/config.json
│   ├── catalog.py           # miloco-cli device catalog + 5s 节流
│   ├── context_injection.py # pre_llm_call 钩子，profile 分级装配上下文
│   ├── tools_notify.py      # miloco_im_push / miloco_notify_bind
│   ├── notify_target.py     # 通知目标解析
│   ├── tools_habit.py       # miloco_habit_suggest 状态机
│   └── cron_setup.py        # 4 个受管 cron reconcile
├── adapter/                 # 入站适配进程，把 miloco webhook 翻译成 Hermes turn
│   ├── __main__.py          # 入口：python -m adapter
│   ├── server.py            # aiohttp: POST /miloco/webhook {action,payload} → {code,data}
│   ├── hermes_client.py     # 调 Hermes api_server /v1/chat/completions
│   └── session_map.py       # (sessionKey, lane) → Hermes session_id 确定性映射
├── scripts/
│   ├── sync-skills.py       # 把 plugins/skills/miloco-* 同步到 skills/
│   ├── install.sh           # 高级/手动安装（不 patch、不启 adapter）
│   └── miloco-adapter.sh    # adapter 生命周期管理（start/stop/restart/status/logs/env）
├── skills/                  # sync-skills.py 生成的 16 个 miloco-* skill（gitignore）
└── tests/
    ├── conftest.py
    ├── test_context_injection.py
    ├── test_session_map.py
    ├── test_adapter_contract.py
    └── test_install_e2e.sh  # install-hermes.sh + miloco-adapter.sh 端到端测试（22 断言）
```

---

## 手动 / 高级安装

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

---

## 与 OpenClaw 版的差异（已知降级）

1. **context 注入位置**：Hermes `pre_llm_call` 只能往 **user message** 注入 `{"context": text}`（为保 prompt cache，不污染 system prompt）。OpenClaw 的 `before_prompt_build` 是往 system prompt 追加。功能等价，但注入位置不同。
2. **observability 降级**：`get_trace` 在 Hermes 下直接回 `done`，不回传 turn 元数据，故 miloco 后端的 `agent_runs` 端到端追踪链路不完整。
3. **上下文溢出自愈**：Hermes api_server 无 session 删除/重置路由，识别溢出错误文案后丢弃会话上下文、用无 `X-Hermes-Session-Id` 的全新 turn 重试一次（近似 OpenClaw 的 `deleteSession + re-run`，但丢掉该会话此前记忆）；溢出信号靠错误文案匹配，识别范围偏宽。
4. **通知投递**：`miloco_im_push` 经 Hermes 内置 `send_message` tool 投递；未绑定通知目标时不 fallback 到「最近活跃 channel」（Hermes SessionDB 无 OpenClaw 的 lastTo/lastChannel 结构），而是返回 `needsBind:true` 引导用户先 `miloco_notify_bind`。

以上 3、4 项依赖 Hermes 实例实测，已标 best-effort。

---

## 验证

```bash
# 单测（pytest，Python 端到端契约）
pytest plugins/hermes/tests/test_*.py

# 安装 e2e（bash，install + adapter 全生命周期）
bash plugins/hermes/tests/test_install_e2e.sh

# 出站冒烟（需 Hermes 已启动 + 插件已装）
hermes chat -q "把客厅灯打开" -Q   # -Q 非交互静默模式

# 确认 cron
hermes cron list   # 应见 4 个 [miloco:home-profile] 任务
```

### 已实测验证（Hermes v0.10.0 + GLM via bigmodel OpenAI 端点）
- 出站：插件加载（`hermes plugins list` 显示 enabled）、16 skill 可用、`pre_llm_call` 钩子触发注入设备目录/家庭档案、4 个受管 cron 注册并按计划触发、`miloco-devices` skill 被 agent 正确调用并执行 `miloco-cli`（缺 miloco-cli 时优雅降级）。
- 入站：miloco `{action:"agent",payload}` → 适配器 → Hermes `/v1/chat/completions` 同步 turn → `{code:0,data:{runId,status:"ok"}}`；幂等/`get_trace`/未知 action/鉴权失败 各分支均符合契约。
- 单测：29 pytest + 22 e2e 断言全过。
- 待用户环境补齐：miloco 后端 + 小米账号（真实设备控制链路 `skill → miloco-cli → 后端 → 设备`，此链路与 OpenClaw 版完全相同）。

### Hermes 侧需注意
- **croniter**：Hermes v0.10.0 的 cron 调度需 `pip install croniter`（管理 cron 表达式），否则 4 个受管任务创建失败。
- **api_server 启用**：`~/.hermes/.env` 设 `API_SERVER_KEY=<密钥>` 即自动启用 api_server 平台（默认端口 8642），适配器据此驱动 turn。
- **模型**：Hermes 的 `custom` provider 对非 openai.com 域名按 host 推导 env（如 bigmodel → `BIGMODEL_API_KEY`），或在 `config.yaml` 的 `model.api_key` 直接写 key 最稳。

详见 `knowledge/03-features/hermes-integration.md`。

---

## 给 AI agent 的安装 Prompt

把下面整块（从 `---` 开始到 `---` 结束）发给 Hermes / Claude / Codex 等 AI agent，它就能照着做：

---

请帮我把 `miloco × Hermes Agent` 兼容层装到本机的 Hermes 上。装好之后我会自己试。

**仓库**：<https://github.com/n0tssss/xiaomi-miloco>

**完整文档**：<https://github.com/n0tssss/xiaomi-miloco/blob/main/plugins/hermes/README.md>

**前置假设**（先 `command -v` 验证，缺什么告诉我）：

- 我已经装了 Hermes Agent（`~/.hermes` 存在，`hermes` CLI 在 PATH）
- 我已经装了 miloco 后端（`miloco-cli` 在 PATH，`$MILOCO_HOME/config.json` 存在）
- `python3` 在 PATH

**你的步骤**（详细见上面 README 的 "If you're an AI agent" 段）：

1. 让我先 `git clone https://github.com/n0tssss/xiaomi-miloco.git` 拉到本地
2. `cd xiaomi-miloco`
3. `bash plugins/hermes/install-hermes.sh` 跑一键安装
4. `bash plugins/hermes/tests/test_install_e2e.sh` 跑 e2e 校验，22 断言全过才算好
5. `hermes gateway restart` 重启 Hermes 让插件生效
6. `hermes plugins list` 确认 `miloco` enabled
7. `ls ~/.hermes/skills/miloco-*` 确认 16 个 skill
8. `bash plugins/hermes/scripts/miloco-adapter.sh status` 确认 adapter 在跑
9. **回报给我**：按 README 里"装完回报给用户"的格式，告诉我在哪看 PID/日志/miloco config.json 备份，以及怎么回滚

**任何一步失败**：先看 README 的 Troubleshooting 表，必要时 `bash plugins/hermes/scripts/miloco-adapter.sh logs` 看 adapter 日志、`hermes --help` 看可用命令。

**不要做**：不要 commit、不要 push、不要改我仓库里的代码、除非我明确说要。

---
