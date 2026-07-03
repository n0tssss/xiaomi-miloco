# pr-hermes 自测覆盖报告

> 你之前问:"你如何自测的,都没配置啊"
> 这份文档**诚实答**: 74 个 pytest + 14 项 diagnose + 几次真发 IM,**但都不是** end-to-end 业务流测试。
> 后端 .env 没配 model key,Xiaomi 账号没绑,感知/规则/任务这些需要 LLM 的链路**全没真验过**。

## 测试矩阵(实际跑过的 vs 跑得通的)

| 维度 | 实际测试 | 覆盖范围 | 文件/命令 |
|---|---|---|---|
| **plugin 加载** | ✅ pytest | 6 个 hook + 3 个 tool 注册 | `plugins/hermes/tests/conftest.py` |
| **tool 可见性** | ✅ hermes chat | agent 看到 im_push / habit_suggest / notify_bind | `hermes chat -q "列出所有miloco_*工具"` |
| **skill 加载** | ✅ hermes chat | 16 个 miloco-* skill 可见 | `hermes chat -q "列出miloco-* skills"` |
| **skill 实际加载** | ✅ hermes chat | agent 调 miloco-devices,正确返回"无设备" | `hermes chat -q "调miloco-devices列设备"` |
| **versions 一致性** | ✅ hermes chat | notify_bind.versions 返回三件套一致 | `hermes chat -q "调notify_bind action=versions"` |
| **notify_bind switch** | ✅ hermes chat | target 切到飞书 + 切回微信 | `hermes chat -q "调miloco_notify_bind action=switch target=..."` |
| **im_push 真发 IM** | ✅ hermes chat | 飞书收到,ok=true,platform=feishu,chat_id 实际存在 | `hermes chat -q "调miloco_im_push发:..."` |
| **backend /health** | ✅ curl | 200 OK | `curl http://127.0.0.1:1810/health` |
| **--diagnose 14 项** | ✅ bash | 全 ✓(结构性:文件/端口/plugin/cron) | `bash install-hermes.sh --diagnose` |
| **adapter loader duck-typed** | ✅ pytest | 20 个 case,含契约违反/异常/缓存 | `backend/tests/agent_platform/test_loader.py` |
| **hermes_adapter 单元** | ✅ pytest | 28 个 case,URL/overflow/error_text/session_map | `plugins/hermes/tests/test_hermes_adapter.py` |
| **tools_notify resolveNotifyTarget** | ✅ pytest | 5 个 case(显式/fallback/needsBind/损坏/缺) | 同上 |
| **context_injection 行为** | ✅ pytest | 11 个 case,071931f 后 minimal 返 None | `plugins/hermes/tests/test_context_injection.py` |
| **Step 1.10 v2 perception 检测** | ✅ shell 逻辑 | 不会误拷 v1 谎报 v2 | `install-hermes.sh:583` |
| **Zirconi 6/29 review 🔴 4 项** | ✅ 修 + 测 | test_context_injection/troubleshooting/README URL/guide 测试 | commit `c555608` |

## 测试矩阵(没真测的,因 backend .env 没配 model key)

| 维度 | 为什么没测 | 缺失的影响 |
|---|---|---|
| **感知引擎触发** | 需 Xiaomi 账号 + 摄像头 | `miloco-cli perceive query` 永远 0 命中 |
| **规则触发** | 需 cron + 设备 | `miloco home patrol` 0 数据 |
| **任务执行** | 需任务 schema | `miloco-create-task` 仅读 SKILL.md |
| **家庭记忆写入** | 需 home profile 路径 | `home-observe` skill 跑空 |
| **trace meta.json 写盘** | 需真实 backend dispatch_event | 路径架构 OK,但真写盘未验 |
| **agent_meta_poller 读盘** | 同上,需真 meta 文件 | 改 disk IPC 后没真 dispatch 事件 |
| **multi-turn context 缓存命中** | 需多次同一 session chat | cache 收益未量化 |
| **真实小米账号 OAuth** | 需扫码 | `account bind` 流程未跑 |
| **perception ONNX 模型** | 4 个模型 ~80MB | fork 仓库的 `backend/.../perception/models/` 有,Step 4.7 同步,链路未跑通 |
| **感知后端 dispatch → agent → IM 推送 全链路** | 需 model + 设备 + 摄像头 | 这是最关键漏验的链路 |

## 结论

**自测覆盖范围**:
- ✅ **结构性** + **新架构骨架** + **少量真实 IM 投递**
- ❌ **end-to-end 业务流**(perception → rule → task → IM)

**对用户的影响**:
- 如果你只跑结构诊断(看 --diagnose),**一切 ✓**
- 如果你跑实际功能(感知事件 → 推送),**backend 没 model key 会失败**
- 如果要真业务流,需要:① Xiaomi 账号绑定(`miloco-cli account bind`)+ ② Omni API key(填 .env)+ ③ 摄像头权限 + ④ 触发感知事件

**补自测建议**(下个 session):
1. `pytest tests/test_e2e_limitations.py` — 跑一遍验证 .env 缺失时 backend 优雅降级
2. `bash tests/test_e2e_real.sh` — 实际通过 hermes chat 跑一次 im_push,断言飞书收到
3. `bash tests/test_e2e_diagnose.sh` — diagnose 14 项

**为什么不现在就补全自测**:
- 没 .env = 没 model key = 跑业务流测会全 fail,补了也是空
- 需要用户先填 .env(或者暂时 mock LLM)
- 我会写一个 `pytest mock_llm.py fixture`,临时 mock LLM 响应,跑业务流覆盖 — 但这是**新工作**,非"补自测"

## 附:不是 bug 是设计 — 已知不测

- backend `uvicorn` 起得来 ≠ LLM 调得通
- `adapter.send_turn()` 200 ≠ plugin 实际能感知事件
- `hermes chat -q "ping"` 200 ≠ 实际家庭记忆写入

这些是**所有 hermes-pr.md 文档里都没明示**的事。doc 主线 #1+#2+#4+#11 全做完,但**没有 .env 就只能验证架构层**。
