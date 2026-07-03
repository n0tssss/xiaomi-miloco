# plugins/<runtime>/ 规范

## 目录布局

```
plugins/
├── openclaw/    # 官方默认 agent runtime(TypeScript + 小米 OpenClaw)
├── hermes/      # 开源 agent runtime(Python + NousResearch Hermes Agent) 【hermes-pr.md 落地】
└── <next>/      # 未来 runtime 模板参考此布局
```

每个 runtime 必须:
- 自包含(plugin / adapter / install 脚本 / tests)
- 命名 runtime 目录为单数(`hermes/` 不 `hermes-plugin/`)
- 不动 `backend/` 后端代码、不动 `openclaw/` 已存在的代码
- 通过 `install-<runtime>.sh` 一键脚本交付

## 子目录标准

```
plugins/<runtime>/
├── README.md                    # 架构图 + 12 项状态 + 与 OpenClaw 差异
├── install-<runtime>.sh         # 一键脚本(幂等,可重跑)
├── miloco-plugin/               # 业务逻辑(skills / tools / hooks)
│   ├── __init__.py
│   ├── tools_<feature>.py        # 工具实现
│   ├── context_injection.py      # profile 判定 + 块构造
│   ├── trace.py                  # trace 钩子
│   └── cron_setup.py             # 受管 cron reconcile
├── skills/                      # 由 install 脚本 cp 到 runtime 的 skills 目录
├── adapter/                     # 【仅 PR #279 老架构需要,主线 #1 后可删】(hermes 已删)
│                                # 不需要 adapter 进程就走 backend 直调架构
└── tests/                       # pytest 覆盖
```

## `install-<runtime>.sh` 标准

1. 前置检查(python/runtime-cli/`<MILOCO_HOME>`/`<MILOCO_HOME>/config.json`)
2. 同步 16 个 miloco-* skill → `<runtime_home>/skills/`
3. cp miloco-plugin → `<runtime_home>/plugins/miloco/miloco-plugin/`
4. 【主线路由】cp `<runtime>_adapter/` → `<MILOCO_HOME>/agent_platform/<runtime>/` + 写 `config.json::agent.platform=<runtime>`
5. ONNX 模型同步 → `<MILOCO_HOME>/models/`
6. 写 `<runtime_home>/.env::API_SERVER_KEY`
7. register plugin
8. (可选)启动后端 / adapter / 重启 runtime
9. 记录 versions → plugin state.json

## agent platform 抽象(主线 #1 后)

backend 不写平台相关代码,通过 `AgentPlatformAdapter` 抽象:

```python
# backend/.../agent_platform/base.py
class AgentPlatformAdapter(ABC):
    name: str

    @abstractmethod
    async def send_turn(self, ctx: TurnContext) -> AgentTurnResult: ...

    @abstractmethod
    async def read_trace_meta(self, run_id: str) -> TraceMeta | None: ...

    @abstractmethod
    def build_system(self, profile: str, extra: dict) -> str: ...
```

**Plugin 侧实现**:`plugins/<runtime>/<runtime>_adapter/adapter.py`
- duck-typed(5 方法契约,不强制继承)
- 由 `install-<runtime>.sh` Step 4.x cp 到 `<MILOCO_HOME>/agent_platform/<runtime>/`
- backend `agent_platform/loader.py` 动态 import

## 与 OpenClaw 的关键差异参考

| 维度 | OpenClaw | Hermes |
|---|---|---|
| 语言 | TypeScript | Python |
| 上下文注入通道 | `before_prompt_build` → system prompt | `AgentPlatformAdapter.build_system()` → OpenAI `<system>` 消息 |
| 入站回调 | 插件内 `registerHttpRoute` | backend `AgentPlatformAdapter.send_turn()` 直调 |
| 同步等 turn | `api.runtime.subagent.run` + `waitForRun` | `/v1/chat/completions` 同步 |
| backend 生命周期 | OpenClaw 帮管 | runtime `register()` 拉起(`miloco-cli service restart`) |

## 添加新 runtime 的 checklist

1. `plugins/<runtime>/README.md` 写清楚架构图(参考 hermes 的)
2. `plugins/<runtime>/install-<runtime>.sh` 按 9 步标准写
3. `plugins/<runtime>/<runtime>_adapter/adapter.py` 实现 5 方法
4. `plugins/<runtime>/tests/test_<feature>.py` 覆盖关键功能
5. `knowledge/03-features/<runtime>-integration.md` 写架构 + 与 OpenClaw 差异
6. 提交 PR(单主题)

## 现状

| runtime | 状态 | commit |
|---|---|---|
| openclaw | ✅ 默认(原厂支持) | upstream |
| hermes | ✅ 本次 PR 落地(主线 8 项 + plugin 4 项 + 文档 6 项) | pr-hermes 27 commits |
| langchain / crewai / autogen | 未来 | — |