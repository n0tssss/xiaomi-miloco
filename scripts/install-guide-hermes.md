---
name: install-miloco-hermes
description: Miloco Hermes Agent 兼容层安装引导,当用户说"装 miloco for Hermes"时激活。
metadata:
  author: Miloco Team
  last_updated: 2026-07-04
---

# Miloco × Hermes Agent 安装指南

把 Miloco 装到一台**已经装了 Hermes Agent** 的机器上。Hermes 兼容层在本仓库 `plugins/hermes/` 下。

> **Windows 用户:** 当前不支持原生 Windows,请先装 [WSL](https://learn.microsoft.com/zh-cn/windows/wsl/install),在 WSL 终端中执行。

> **agent 是主操作员**:下面 3 步里 agent 自跑命令、不需要用户在终端复制粘贴(**唯一例外 Step 2 重启 gateway**,Hermes 有 anti-restart-loop,agent 不能代跑,下面会标出来)。

---

## Step 1:装插件(agent 自跑)

```bash
git clone https://github.com/XiaoMi/xiaomi-miloco.git
cd xiaomi-miloco
bash plugins/hermes/install-hermes.sh
```

成功标志:脚本打印 `✅ 安装完成(可重复执行,幂等)`。脚本自带 `--diagnose` 子命令可重跑 14 项自检。重跑也是幂等的,自动 recover 半装残留。

---

## Step 2:重启 gateway(用户跑)

Agent **不**跑这步(Hermes 有 anti-restart-loop,agent 调会把自己 session 也踢了):

```bash
hermes gateway restart
```

用户跑完发「好了」给 agent。

---

## Step 3:验证(agent 自跑)

```bash
# 14 项结构性自检
bash plugins/hermes/install-hermes.sh --diagnose
```

期望:`全部 14 项通过 — 推送链路完整`。具体看 adapter (launchd) / adapter /health 是否标 `N/A(新架构,无独立 adapter 进程)` — 这表示**新架构已生效**(主线 #1 完成),不是错。

可手动验证:
- `hermes chat -q "列出所有miloco_*工具"` → 应看到 3 个(im_push / habit_suggest / notify_bind)
- `hermes chat -q "调miloco_notify_bind action=list"` → 应看到当前 IM target + 候选

可手动浏览 `http://127.0.0.1:1810/` 看 dashboard 效果。

---

## 【可选】配米家账号 + Omni 模型

**只跑感知/规则/任务时需要**(纯 chat / im_push 推送 / skill 调试不需要)。

### 1. Omni 模型(LLM 功能,推荐先配)

**L1 守门**:pr-hermes fork 的 `reconcile_cron_jobs` 会检测 `model.omni.api_key`,配齐后 4 个受管 cron 自动 active。没配齐时 cron 保持 paused(避免每 15min 推 [SILENT] 骚扰)。

Agent 跑三条 `config get` 看已配状态:
```bash
miloco-cli config get model.omni.api_key
miloco-cli config get model.omni.model
miloco-cli config get model.omni.base_url
```

**未配置**:发用户下面这段让他选 + 贴值:
> Miloco 的感知引擎需要一个多模态大模型(Omni Model)来理解摄像头画面。
> 默认推荐 **小米 MiMo** 模型,任何 OpenAI 兼容服务都行。
>
> **A. 默认 MiMo**(key 申请:https://platform.xiaomimimo.com):
> ```bash
> miloco-cli config set model.omni.api_key "<key>"
> ```
>
> **B. 第三方多模态**(OpenAI / Anthropic 兼容 / 自建 / vllm / ollama):
> ```bash
> miloco-cli config set \
>   model.omni.api_key "<key>" \
>   model.omni.base_url "<base_url>" \
>   model.omni.model "<model>"
> ```

参考 `backend/.env.example` 看完整 3 provider 示例。

配完后 agent 重启 backend:
```bash
miloco-cli service restart
```

### 2. 米家账号(感知/规则用,模型配好后再做)

Agent 跑:
```bash
miloco-cli account status
```

- **`is_bound: true`**:跳过。
- **`is_bound: false`**:发用户 OAuth 链接(`miloco-cli account status` 输出里有 `bind_url`),等用户把授权后跳到 `mico.api.mijia.tech/login_redirect` 的 URL 里 `code=` 后那串 base64 贴回来。Agent 自跑:
  ```bash
  miloco-cli account authorize "<base64>"
  miloco-cli account status   # 验证 is_bound: true
  ```
  base64 5 分钟过期,过期就再让用户重新拿一次。

### 3. 设备准备(感知数据来源)

用 **米家 App** 登录同账号(同 miloco OAuth 那个账号),设备会自动出现在 miloco 后端。验证:
```bash
miloco-cli device list
```

## 配齐后的自动行为

`reconcile_cron_jobs` 跑时检测 backend ready(model.omni.api_key 配齐)→ 4 个受管 cron 自动 update 为 active,无需用户手动 `hermes cron resume`。配置即生效。

---

## 故障排除

| 问题 | 解法 |
|---|---|
| `miloco-cli: command not found` | `curl -LsSf https://github.com/XiaoMi/xiaomi-miloco/releases/latest/download/install.sh \| bash -s -- --agent-prepare` |
| `git clone` 失败 | `git config --global url."https://ghproxy.com/`.insteadOf https://` 走镜像 |
| 装到一半退出 | `bash plugins/hermes/install-hermes.sh` 重跑(幂等自动 recover) |
| `No module named aiohttp` | `pip install aiohttp httpx croniter` 后重跑 install-hermes.sh |
| `hermes cron list` 没 4 个 miloco 任务 | `pip install croniter` + 重跑 install-hermes.sh(Step 8.5 reconcile 兜底) |
| `miloco_im_push` 报 `no deliver target` 或 `needsBind:true` | 在 Hermes 里连 IM(`hermes config set feishu.app_id ...`)+ 重跑 install-hermes.sh,或 `miloco_notify_bind action=switch target=...` |
| `--diagnose` 报 adapter (launchd) N/A | **正常** — 新架构(`hermes-pr.md` 主线 #1 完成)删了独立 adapter 进程,backend 直调 |
| 感知事件不触发 | 大概率 `.env` 没配或 Xiaomi 账号没绑。`miloco-cli account status` + `miloco-cli config get model.omni.api_key` 验证 |
| 单路开关(单独关视频/音频)不工作 | 需 fork 仓库 backend 真正含 v2 perception(`video_enabled`/`audio_enabled` 字段)。`hermes-pr.md` 🟡 #5 留给 miloco 团队 |

## 架构简图(理解为什么 `--diagnose` 报 adapter N/A 是对的)

```
miloco backend (FastAPI, uv tool venv)
  AgentDispatcher → AgentPlatformAdapter → HermesAdapter → POST Hermes :8642/v1/chat/completions
                                                                              ↓
                                                                       LLM (MiMo / 自配)
                                                                              ↓
                                                                       用户 IM (weixin/feishu/...)
```

`hermes-pr.md` 主线 #1+#2+#4+#11+#1 完成:**无独立 adapter 进程**,backend 直调 hermes。详见 `plugins/hermes/README.md` 与 `knowledge/03-features/hermes-integration.md`。