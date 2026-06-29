---
name: install-miloco-hermes
description: Miloco Hermes Agent 兼容层安装引导，当用户说 "装 miloco for Hermes" 时激活。
metadata:
  author: Miloco Team
  last_updated: 2026-06-25
---

# Miloco × Hermes Agent 安装指南

把 Miloco 装到一台**已经装了 Hermes Agent** 的机器上。Hermes 兼容层在 fork `n0tssss/xiaomi-miloco` 的 `plugins/hermes/` 下。

> **Windows 用户：** 当前不支持原生 Windows，请先装 [WSL](https://learn.microsoft.com/zh-cn/windows/wsl/install)，在 WSL 终端中执行。

> **agent 是主操作员**：下面 4 步里 agent 自跑命令、不需要用户在终端复制粘贴（**唯一例外 Step 3 重启 gateway**，Hermes 有 anti-restart-loop，agent 不能代跑，下面会标出来）。

---

## Step 1：装插件（agent 自跑）

```bash
git clone https://github.com/n0tssss/xiaomi-miloco.git
cd xiaomi-miloco
bash plugins/hermes/install-hermes.sh
```

脚本会自动：依赖检查、Bearer 复用、16 skill 同步、插件 + adapter 安装、IM 探测、config.json patch、adapter 启动、plugin enable、版本记录。

成功标志：脚本打印 `mark_done 9` 且 exit 0。如果 exit ≠ 0，贴 stderr + 翻底部故障排除表。脚本自带 `--diagnose` 子命令可重跑 12 项自检。重复跑 install-hermes.sh 是幂等的。

---

## Step 2：配置米家账号 + Omni 模型

两个都要配置（顺序：账号 → 模型）。

### 2.1 米家账号

Agent 跑：

```bash
miloco-cli account status
```

- **输出含 `is_bound: true`**：账号已绑，跳到 2.2。
- **输出含 `is_bound: false`**：发用户 OAuth 链接 `{bind_url}`（`miloco-cli account status` 输出里有），等用户把授权后跳到 `mico.api.mijia.tech/login_redirect` 的 URL 里 `code=` 后那串 base64 贴回来。Agent 跑：

  ```bash
  miloco-cli account authorize "<base64>"
  ```

  再跑 `miloco-cli account status` 确认 `is_bound: true`。

base64 5 分钟过期，过期就再让用户拿一次。

### 2.2 Omni 模型

Agent 跑：

```bash
miloco-cli config get model.omni.api_key
miloco-cli config get model.omni.model
miloco-cli config get model.omni.base_url
```

**全空**：发用户下面这段让他选：

> Miloco 感知引擎需要多模态大模型来理解摄像头画面。
>
> **A. 默认 MiMo（推荐）**：从 https://platform.xiaomimimo.com 拿 key，贴回我（model/base_url 默认 `mimo-v2.5` / `https://api.xiaomimimo.com/v1`，不必设）
>
> **B. 第三方多模态**（OpenAI / Anthropic / 自建 / 任何 OpenAI 兼容 API）：贴「model 名 / base_url / api_key」三个值
>
> 备注：必须是支持视觉/视频输入的多模态模型，纯文本模型（如 `MiniMax-M3`）会让感知链路挂。

用户回选 + 贴值，Agent 跑：

```bash
# A 路径
miloco-cli config set model.omni.api_key "<key>"

# B 路径
miloco-cli config set model.omni.model "<model>" model.omni.base_url "<base_url>" model.omni.api_key "<key>"
```

**已配置**：直接进 Step 3。

---

## Step 3：重启 gateway

Agent **不**跑这步（Hermes 有 anti-restart-loop，agent 调会把自己 session 也踢了）：

```bash
hermes gateway restart
```

让用户跑，跑完发「好了」给 agent。

---

## Step 4：验证

Agent 自跑：

```bash
# adapter /health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18789/health
# backend /health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:1810/health
# plugin enabled
hermes plugins list --plain --no-bundled | grep miloco
# 16 skill 装上
ls -d ~/.hermes/skills/miloco-* 2>/dev/null | wc -l
# 感知模型齐
ls ~/.openclaw/miloco/models/{det_4C,human_body_reid_v2,bge-small-zh-v1.5-int8,silero_vad}.onnx ~/.openclaw/miloco/models/bge-small-zh-v1.5-tokenizer.json 2>/dev/null | wc -l
# 真调一次感知
miloco-cli perceive query --source <任一在线摄像头 did> --query "画面里有什么？"
```

应全 PASS（perceive query 失败最常见 = Omni 模型不支持视频输入，回到 2.2 换模型）。

装完跑一份 `plugins/hermes/scripts/miloco-status.sh` 一次性 9 项自检，给用户状态报告。

---

## 故障排除

| 问题 | 解法 |
|---|---|
| `miloco-cli: command not found` | `curl -LsSf https://github.com/XiaoMi/xiaomi-miloco/releases/latest/download/install.sh \| bash -s -- --agent-prepare` |
| `~/.openclaw/miloco/config.json: not found` | `export MILOCO_HOME=$HOME/.openclaw/miloco` + `miloco-cli service start`（自动 init） |
| 端口被占（`port already in use`） | `ss -tlnp sport = :1810` 查谁占 + kill |
| `No module named aiohttp` | `pip install aiohttp httpx croniter` 后重跑 install-hermes.sh |
| `git clone` 失败 | `git config --global url."https://ghproxy.com/".insteadOf https://` 走镜像 |
| 装到一半退出 | `bash plugins/hermes/install-hermes.sh` 重跑（幂等自动 recover） |
| 装完 `account status` 仍 `is_bound: false` | base64 5 分钟过期，重拿 |
| 装完 `perceive query` 400/1000 | Omni 模型不支持视频输入，回到 2.2 换多模态模型 |
| `hermes cron list` 没 4 个 miloco 任务 | `pip install croniter` + 重跑 install-hermes.sh |
| `miloco_im_push` 报 `no deliver target` | 在 Hermes 里连 IM（`hermes config set telegram.bot_token ...`）+ 重跑 install-hermes.sh |
| `hermes plugins list` 没 miloco | `bash plugins/hermes/install-hermes.sh` 重跑（幂等自动 enable） |
