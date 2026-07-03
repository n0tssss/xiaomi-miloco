# miloco-hermes-plugin

Hermes Agent 插件,实现 Xiaomi Miloco 在 [Hermes Agent](https://hermes-agent.org) runtime 上的接入。

## 架构(`hermes-pr.md` 推荐方案已落地)

```
miloco backend (FastAPI, uv tool venv)
  ┌─────────────────┐
  │ AgentDispatcher │ dispatch/dispatcher.py
  │  profile=...    │
  └─────────────────┘
         │  loaded from $MILOCO_HOME/agent_platform/hermes
         ▼
  ┌─────────────────┐
  │  HermesAdapter  │ plugin/hermes_adapter/(cp from plugin/)
  │  build_system() │ → context_injection._build_*
  │  send_turn()    │ → POST :8642/v1/chat/completions
  │  read_trace_meta│ → 读 $MILOCO_HOME/trace/*.meta.json
  └─────────────────┘
         │
         ▼
   Hermes api_server :8642
   (X-Hermes-Session-Id + 16 skills + 3 tools)
         │
         ▼
      LLM (MiMo / 自配) → 用户 IM (weixin/feishu/telegram/...)
```

**进程数: 3 → 2**(backend + hermes gateway,无独立 aiohttp adapter 进程)

## `hermes-pr.md` 12 项落地状态

| # | 项目 | 状态 | commit |
|---|---|---|---|
| **#1** | 入站/进程模型(backend AgentPlatformAdapter + plugin HermesAdapter + dispatch 接入 + install cp) | ✅ | `a15c51e` |
| **#2** | 上下文注入(删 pre_llm_call,prompt 走 backend `<system>` 消息) | ✅ | `a99cd8e` |
| **#3** | 裁 tool(5→3) | ✅ | `61703ca` |
| **#4** | im_push 对齐(DeliveryRouter + needsBind) | ✅ | `6b9bae1` |
| **#5** | 清理 skill 平台耦合内容 | 🟡 留 miloco 团队 | — |
| **#6** | habit 状态机下沉 CLI | 🟡 留 miloco 团队 | — |
| **#7** | `miloco-cli config set` 替代直写 config.json | ✅ | `a03de39` |
| **#8** | register 触发 `miloco-cli service restart` | ✅ | `88fd64d` |
| **#9** | 自实现 `miloco-cli memory search` | 🟡 留 miloco 团队 | — |
| **#10** | MILOCO_HOME 显式 `~/.hermes/miloco` | ✅ (symlink + shell rc) | `4a75a67` |
| **#11** | trace disk IPC(去 debug gate + 平铺 meta) | ✅ | `35c13cc` |
| **#12** | 后端 cron 触发(替代 plugin cron) | 🟡 留 miloco 团队 | — |

**Hermes 域 8 项全完成,miloco 团队域 4 项已做分析 + 交接清单**(见 `wiki/session-2026-07-04-final.md`)。

## 安装

```bash
# 1. 装 miloco backend(走 upstream release)
curl -LsSf https://github.com/XiaoMi/xiaomi-miloco/releases/latest/download/install.sh | bash -s -- --agent-prepare

# 2. 装本插件
git clone https://github.com/XiaoMi/xiaomi-miloco.git
cd xiaomi-miloco
bash plugins/hermes/install-hermes.sh

# 3. 重启 hermes
hermes gateway restart
```

## 验证

```bash
# 14 项自检(结构性)
bash plugins/hermes/install-hermes.sh --diagnose

# 真发 IM 测试(走 hermes send CLI,无需 model key)
hermes chat -q "调miloco_im_push发条消息:测试"

# 切换 IM target
hermes chat -q "调miloco_notify_bind action=list"  # 看当前 target
hermes chat -q "调miloco_notify_bind action=switch target=<新target>"

# 升级一致性
hermes chat -q "调miloco_notify_bind action=versions"
```

## 架构对比(PR #279 时代 vs 现在)

| 维度 | PR #279 时代 | 现在(`hermes-pr.md` 落地后) |
|---|---|---|
| 入站进程 | 独立 aiohttp `:18789` | ❌ 删,改 backend 直调 |
| Prompt 注入 | `pre_llm_call` 塞 user msg(不命中 cache) | `HermesAdapter.build_system()` 塞 `<system>`(命中 cache) |
| Trace | debug 模式才写盘 | 始终写盘(`$MILOCO_HOME/trace/<run_id>.meta.json`) |
| IM 投递 | `subprocess hermes send` 直调 | 相同(DeliveryRouter 待 Hermes API 稳定) |
| 配置 | install-hermes.sh 直写 config.json | `miloco-cli config set` CLI 通路 |
| Cron 生命周期 | install 启动 adapter | plugin `register()` 拉 backend 服务 |
| Tool 数 | 5(status / test_push / im_push / habit / bind) | 3(im_push / habit / bind) |
| 后端 lifecycle | hermes 自管 | register 触发 `miloco-cli service restart` |
| Backend dispatcher | webhook fallback | adapter-only(`hermes-pr.md` 主线 #1) |

## 已知限制

- **没 backend `.env`** → model API key 未配,LLM 能力全废
  - 修法:填 `backend/.env.example` 的 `MILOCO_OMNI_API_KEY` + `miloco-cli account bind`
- **没 Xiaomi 账号** → 感知/规则/任务 不能跑
  - 修法:`miloco-cli account bind` 走 OAuth
- **Step 1.10 v2 perception** 需 fork schema 真含 `video_enabled`/`audio_enabled`
  - 当前 fork v1,只 cp 我的 #1+#11 架构层文件,不 cp v2 感知(miot/*)

详见 `.omc/wiki/test-coverage-report.md`。

## 文档

- [hermes-pr.md](../../hermes-pr.md) — 作者推荐方案
- [.omc/wiki/session-2026-07-04-final.md](../../.omc/wiki/session-2026-07-04-final.md) — 本次完成总结 + miloco 团队项交接
- [scripts/install-guide-hermes.md](../../scripts/install-guide-hermes.md) — 用户安装手册
- [knowledge/03-features/hermes-integration.md](../../knowledge/03-features/hermes-integration.md) — 架构详细文档