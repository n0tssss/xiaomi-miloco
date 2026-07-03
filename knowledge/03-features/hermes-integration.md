# Hermes Agent 集成

## 背景与目标

miloco 原本只通过 OpenClaw 插件(`plugins/openclaw/`)接入小米内部的 OpenClaw agent 运行时。
为支持开源生态,fork 新增 `plugins/hermes/`,把同样的双向集成移植到 [Hermes Agent](https://github.com/NousResearch/hermes-agent)(Nous Research 的开源 Python agent,内置 `hermes claw migrate` 迁移路径)。

两条集成路径并列、互不影响,用户按自己装的 agent 运行时二选一。

---

## 产品面

能力与 OpenClaw 版一致:
- **自然语言控制设备**:对 Hermes 说意图,miloco-* skill 经 `miloco-cli` 调后端 API。
- **创建持久任务**:rule / cron / record 组合。
- **主动感知回调**:规则触发、设备绑定、感知告警时,后端经 `AgentPlatformAdapter` 投递 DYNAMIC 回调给 Hermes,agent 在对应会话自主决策。
- **家庭记忆管理**:对话写入档案,`<system>` 消息把档案注入上下文(从 `pre_llm_call` 改的)。
- **后台知识整理**:4 个受管 cron(perception-digest / home-patrol / home-dreaming / habit-suggest)。

---

## 研发面

### 架构(数据流)

#### Agent → Miloco(出站)

```
用户对话
  → Hermes 选 miloco-* skill(/skills 或自然语言)
  → miloco-cli 调 HTTP API(Authorization: Bearer <token>)
  → MiotService / RuleService / PersonService / TaskService
```

#### Miloco → Agent(入站回调)

```
感知结果 / 规则触发 / 设备绑定
  → AgentDispatcher(dispatch/dispatcher.py,单飞+合并+优先级淘汰)
  → adapter = load_adapter() ← $MILOCO_HOME/agent_platform/hermes/
  → run_agent_turn → adapter.send_turn(TurnContext)
  → HermesAdapter → POST Hermes :8642/v1/chat/completions
     (OpenAI 兼容,带 system msg + X-Hermes-Session-Id 会话连续)
  → agent 跑 miloco-notify 或其它 skill
  → 异步 trace.py 写盘 $MILOCO_HOME/trace/<run_id>.meta.json
  → backend AgentMetaPoller.poll_once 读盘 → metrics_client.record_agent_run
```

### 插件注册点(`plugins/hermes/miloco-plugin/`)

`register(ctx)` 注册:
1. **触发 miloco backend 启动** — `subprocess.run(["miloco-cli", "service", "restart"])`,保证 backend 在线
2. **6 个 trace hooks**(`pre/post_llm_call` + `pre/post_tool_call` + `on_session_start/end` + `register_trace_link`)
3. **3 个 tool**:`miloco_im_push` / `miloco_habit_suggest` / `miloco_notify_bind`
4. **4 个受管 cron reconcile** — 启动时按 `[miloco:home-profile]` 标签对齐

### 入站 Adapter 抽象(`backend/miloco/src/miloco/agent_platform/`)

【`hermes-pr.md` §五 #1 推荐架构】Backend 通过 `AgentPlatformAdapter` 抽象入站,**不再依赖独立 aiohttp 进程**:

- **框架层**(`base.py`):`TurnContext` / `AgentTurnResult` / `TraceMeta` / `AdapterTransportError`
- **loader.py**:duck-typed 加载 — `importlib.util` 从 `$MILOCO_HOME/agent_platform/<name>/adapter.py` 动态 import
  - 接受任何暴露 5 方法(`name` / `send_turn` / `read_trace_meta` / `build_system` / `aclose`)的类
  - 缺方法、import 抛错、契约不符 → 返 None 不抛(让 backend 降级到 webhook 模式 — webhook 模式也已删,实际是拒绝 send)
- **HermesAdapter**(`plugins/hermes/hermes_adapter/`):
  - `build_system(profile, extra)`:从 `context_injection._build_prepend/_build_append` 拼 OpenAI `<system>` 消息
  - `send_turn(ctx)`:POST `:8642/v1/chat/completions`,带 `X-Hermes-Session-Id: miloco:<sessionKey>:<lane>`
  - 溢出自愈:best-effort 关键词检测 + 无 session 头重试一次
  - `read_trace_meta(run_id)`:读 `$MILOCO_HOME/trace/<run_id>.meta.json` 平铺路径

### 与 OpenClaw 集成的关键差异(`hermes-pr.md` 主线完成后)

| 维度 | OpenClaw 版 | Hermes 版(主线 #1 后) |
|---|---|---|
| 插件语言 | TypeScript | Python |
| 上下文注入 | `before_prompt_build` → system prompt | `HermesAdapter.build_system()` → OpenAI `<system>` 消息(命中 cache) |
| 入站回调 | 插件内 `api.registerHttpRoute` | **无独立进程**,backend `AgentDispatcher` → `AgentPlatformAdapter.send_turn()` |
| 同步等 turn | `api.runtime.subagent.run` + `waitForRun` | Hermes api_server `/v1/chat/completions`(`X-Hermes-Session-Id` 会话连续) |
| get_trace | 内存 buffer,后端反向轮询 | 文件 IPC:`plugin trace.py 写盘` ↔ `backend agent_meta_poller 读盘` |
| 溢出自愈 | `deleteSession({deleteTranscript:true})` + 重跑 | 无 session 头全新 turn 重试一次 |
| 通知投递 | `subagent.run({deliver:true})` | `subprocess hermes send` CLI(`send_message` tool 被 Hermes 移除) |
| backend 生命周期 | 有(OpenClaw 帮管) | plugin `register()` 拉起(miloco-cli service restart) |
| 工具数 | 3 | 3(裁了 status / test_push) |
| Adapter 进程 | 独立 aiohttp `:18789` | ❌ **删了** — `hermes-pr.md` 推荐架构 |

### 配置共享

三端(backend / CLI / 插件)共用 `$MILOCO_HOME/config.json`:
- `server.token`:backend 独占生成,CLI/插件只读。
- `agent.platform=hermes`:必填,backend 据此加载 Adapter(由 `install-hermes.sh` Step 4.8 写)。
- `agent.webhook_url` / `agent.auth_bearer`:PR #279 时代用,主线 #1 完成后**已删 backend fallback** — webhook 路径无 listener,这两字段只是历史遗留。

### 已知限制(本 fork 当前状态)

- **backend `.env` 未配** — `MILOCO_OMNI_API_KEY` 空,LLM 能力全废(但 `/health` 200、`agent_platform/adapter` 加载、hermes chat 全 ok)
- **Xiaomi 账号未绑** — 感知/规则/任务不能跑
- **perception ONNX 模型 ~80MB** — `backend/.../perception/models/` 仓库里打包了,`install-hermes.sh` Step 4.7 同步;但链路未真跑

详见 `.omc/wiki/test-coverage-report.md`。

### 如果我要添加/修改 Skill

skill 源在 `plugins/skills/miloco-*`(OpenClaw/Hermes 共用源),改完跑 `plugins/hermes/scripts/sync-skills.py` 重新生成 `plugins/hermes/skills/` 并复制到 `~/.hermes/skills/`。skill 通过 `miloco-cli` 调后端,与 agent 平台无关。

### 出问题排查

- `GET /health` 看 backend 在线。
- `hermes chat -q "调miloco_notify_bind action=versions"` 看三件套一致性。
- `bash plugins/hermes/install-hermes.sh --diagnose` 14 项结构性自检。
- `tail ~/.openclaw/miloco/log/miloco-backend.log` 看 backend 日志。
- `tail ~/.hermes/logs/*.log` 看 hermes 日志。
- 出站 skill 不触发:`hermes chat -q "调miloco-devices列设备"` 确认 skill 已装入 `~/.hermes/skills/`。
- 感知/规则不工作:大概率是 `.env` 没配或 Xiaomi 账号没绑(`miloco-cli account bind`)。