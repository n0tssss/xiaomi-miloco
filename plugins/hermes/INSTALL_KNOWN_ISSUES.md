# Miloco × Hermes 安装流程 — 已知问题清单

> **目标**：让 `git clone && bash plugins/hermes/install-hermes.sh && hermes gateway restart` 一键跑通，无需 agent / 用户手动修补。
>
> **当前实际**：跑完 `install-hermes.sh` 后插件不工作，必须 agent 手动改两处才能用。本清单按"严重程度 + 修复位置"组织，便于另一个 AI 直接据此开 issue / PR。
>
> **适用范围**：`plugins/hermes/` 全部代码 + `scripts/install-guide-hermes.md` + `plugins/hermes/install-hermes.sh`。
> 上游 `scripts/install.py` 暂未触碰（与 OpenClaw install 路径解耦，issue #X 视情况回头提）。

---

## P0 — 装完直接不可用

### #1 `state.json` 路径不一致（最关键）

- **现象**：`install-hermes.sh` 第 4.5 节把 `state.json` 写到 `~/.hermes/plugins/miloco/state.json`，但 plugin 运行时 `tools_notify.py::_state_path(ctx)` 用 `ctx.manifest.path / "state.json"`，实际读的是 `~/.hermes/plugins/miloco/miloco-plugin/state.json`
- **后果**：`miloco_im_push` 永远返回 `{"ok": false, "error": "no deliver target configured..."}`，通知链路整条废
- **修在哪**：`plugins/hermes/install-hermes.sh` 第 4.5 节
- **改法**：`PLUGIN_STATE="$HERMES_PLUGINS_DIR/state.json"` → `PLUGIN_STATE="$HERMES_PLUGINS_DIR/miloco-plugin/state.json"`，跟 `_state_path` 对齐
- **验证**：`cat ~/.hermes/plugins/miloco/miloco-plugin/state.json` 应存在并含 `deliver.target`

### #2 Plugin 装完默认未启用

- **现象**：`hermes.plugins` 是 opt-in 设计，新装 plugin 不自动加入 `~/.hermes/config.yaml` 的 `plugins.enabled` 列表
- **后果**：gateway 重启前后 plugin 都不加载，`miloco_im_push` 工具根本不在 toolset 里，agent 找不到工具
- **修在哪**：`plugins/hermes/install-hermes.sh`（adapter 启动之后、退出之前）
- **改法**：追加 `hermes plugins enable miloco/miloco-plugin`（idempotent：未启用才 enable，已启用跳过）
- **附加**：脚本退出时 echo 当前 `hermes plugins list --enabled` 的 miloco 行作为可见性证据

---

## P1 — 流程卡顿 / agent 装不完

### #3 `install-hermes.sh` adapter 启动 race condition

- **现象**：`nohup python -m adapter &` 后 `sleep 2` 然后查端口；冷启动时 adapter 还没绑定端口，脚本误报"启动失败"
- **日志自相矛盾**：脚本说失败，但 `miloco-adapter.log` 显示 "adapter listening host=127.0.0.1 port=XXXX"
- **后果**：`install-hermes.sh` exit code ≠ 0 → agent 看到失败 / e2e 测试稳定挂
- **修在哪**：`plugins/hermes/install-hermes.sh` adapter 启动 + 端口探测那段
- **改法**：把 `sleep 2; pid=$(get_pid_by_port ...)` 换成 retry loop：最多 10s，每 0.5s 查一次，3 次连续失败才报失败
- **额外**：失败时 echo 完整 log 路径 + 最后 20 行内容，不要让 agent 自己去找

### #4 4.5 节 IM 探测只看 `~/.hermes/config.yaml`，错过实际已连的 IM

- **现象**：用户已接好飞书 / 微信（home channel 状态 `Connected ✓`），但 `config.yaml` 里没有 `feishu:` / `weixin:` 段（它们的配置存在 `auth.json` 或 `FEISHU_HOME_CHANNEL` 等环境变量里）
- **后果**：install 报"未检测到 Hermes 已配置的 IM 平台"，state.json 不写，#1 修了也仍然没 `deliver.target`
- **修在哪**：`plugins/hermes/install-hermes.sh` 第 4.5 节 python helper
- **改法**：探测顺序改为
  1. 调 `hermes platforms list --json` 拿真连接列表
  2. fallback 检查 `auth.json` 的 `providers.feishu` / `providers.weixin`
  3. 再 fallback 当前 config.yaml 扫描
  4. 都没找到就 warn，但仍把空 state.json 写出来（`deliver.target=null` 显式标记，让 plugin 报错更明确）
- **Bonus**：探测到多个 IM 时不要取第一个，把列表写到 `state.json.candidates`，plugin 端提供 `set_deliver_target` 让用户在 miloco-miot-admin 切换

### #5 `hermes gateway restart` 必须在 gateway 进程外

- **现象**：agent / cron session 里跑 `hermes gateway restart` 被 anti-restart-loop 拒绝（"Refusing to restart the gateway from inside the gateway process"）
- **后果**：最后一步 agent 不能代跑，必须用户手动
- **不是 bug**：是 Hermes 自身的安全设计
- **改在哪**：`plugins/hermes/install-hermes.sh`（脚本末尾）
- **改法**：脚本最后 echo 显眼的 `⚠️ 现在请你自己终端跑：hermes gateway restart`，独立一块、加边框、加 ANSI blink 或颜色加重（不是单纯塞在 guide 里让人容易漏看）

---

## P2 — 体验 / 可观测性

### #6 4.5 节 CANDIDATES 顺序对国内用户不友好

- **现象**：当前 `CANDIDATES = ("telegram", "feishu", "wecom", "discord", "slack", ...)` 把 telegram 放第一
- **后果**：国内用户的 telegram 段（如果有）会抢在 feishu / weixin 前面
- **改法**：把 `weixin` 加入 CANDIDATES 第一位（`weixin, feishu, wecom, telegram, ...`）

### #7 `install-hermes.sh` 没进度可视化

- **现象**：脚本只 echo `[✓] xxx`，没有总步骤数，agent / 用户看不到跑到第几步
- **改法**：所有步骤加 `[1/7]` `[2/7]` … 前缀；adapter 启动那段加 spinner / retry 计数 `等待端口 (1/20)...`

### #8 `install-hermes.sh` 失败回滚不完整

- **现象**：`set -e` 退出会留下半装状态（plugin 复制了 + .env 写了 + config.json patch 了，但 adapter 没起来）
- **后果**：用户下次跑 install-hermes.sh 时 6/7 完成，剩 adapter；可能误以为装好了
- **改法**：每步前打桩记录"已生效步骤"，失败时 trap 打印
  ```
  [!] 已生效: 1,2,3,4 (config已patch, .env已写)
      未生效: 5,6,7
  ```
  明确告诉 agent / 用户当前状态

### #9 `--agent-prepare` JSON 暴露敏感字段

- **现象**：`account.user` 段输出完整 `uid / nickname / icon URL / union_id`
- **影响**：agent 把 JSON 贴到 chat / log 时泄露 OAuth identity
- **改法**：mask uid（保留前 4 后 2）、完全删除 union_id、icon URL 保留但加注释"仅前端展示，不要往 IM 发"

### #10 e2e 测试 `test_install_e2e.sh` 因 `set -u` 中途 abort

- **现象**：测试 `set -uo pipefail`，install 失败时 `PID1=` 没赋值，后续 `[ -n "$PID1" ]` 直接触发 unbound variable，整个测试退出不打印 fail 总结
- **改法**：每个赋值前 `PID1=$(cat ... 2>/dev/null || echo)`；或者改用 `set -eo pipefail`（不要 `-u`）

---

## P3 — 长期稳健性

### #11 升级重装丢失 `state.json`

- **现象**：`install-hermes.sh` 第 4 节有 `rm -rf "$HERMES_PLUGINS_DIR/miloco-plugin"`（强删），state.json 跟着没了
- **改法**：删之前 `cp state.json state.json.bak-<ts>`；复制完新 plugin 后如果 bak 存在，merge 旧 `deliver.target` 到新 state.json（除非用户传 `--reset-deliver`）

### #12 config.json backup 文件名只精确到秒

- **现象**：`config.json.bak-20260622-104609`，30s 内 reinstall 会撞名覆盖
- **改法**：加 PID 或毫秒 `config.json.bak-20260622-104609-123456-pid1234`

### #13 pyc 没预编译，冷启动 adapter 慢

- **现象**：plugin 复制后首次 `python -m adapter` 要 import ~10 个模块，慢 ~2s
- **改法**：复制完跑 `python -m compileall "$HERMES_PLUGINS_DIR/miloco-plugin" "$HERMES_PLUGINS_DIR/adapter"` 预编译

### #14 adapter 模块名 `adapter` 容易撞名

- **现象**：用 `python -m adapter` 启动，如果用户 hermes 配置里也有 `adapter/` 子目录会冲突
- **改法**：adapter 内部包改 `miloco_adapter/`，`__main__.py` 改成 `python -m miloco_adapter`，同步 install-hermes.sh 里的启动命令

### #15 `install-guide-hermes.md` 与 `install-hermes.sh` 行为漂移

- **现象**：guide 说"装完 `hermes plugins list | grep -i miloco` 应该看到"，但实际需要先 `hermes plugins enable`（#2），guide 没提
- **改法**：把 guide 改成"由 install-hermes.sh 输出"的反向工程 —— guide 内容 = 脚本实际行为的快照；或者文档与脚本同 repo 强制每次 PR 同步更新

### #16 home-profile pre-injected devices catalog 跟实时不一致

- **现象**：devices catalog 是高频子集 + 生成时刻快照，agent 据此发命令时设备可能已重命名 / offline
- **不是 install 脚本的事**，是 miloco-cli / plugin 端的事
- **改法**：catalog header 加 `last_synced_at` + 强制提示"agent 执行命令前 device list 拉全量"

---

## 优先级建议

| 顺序 | Issue   | 理由                                            |
| ---- | ------- | ----------------------------------------------- |
| 1    | #1      | 修完 install 一装完 `miloco_im_push` 就能用     |
| 2    | #2      | 修完 plugin 真的会被加载                        |
| 3    | #3      | 修完 install-hermes.sh 退出码稳定为 0           |
| 4    | #4      | 修完 state.json 自动带 deliver.target，无需手动 |
| 5    | #6      | 改一行，影响大                                  |
| 6    | #5      | 文档层面提醒                                    |
| 7    | #7-#10  | 体验 / 可观测性补丁                             |
| 8    | #11-#16 | 长期稳健性                                      |

---

## 修完 #1 + #2 + #3 + #4 之后的安装流程

```bash
git clone https://github.com/n0tssss/xiaomi-miloco.git
cd xiaomi-miloco
bash plugins/hermes/install-hermes.sh
# → 自动 patch config.json + 写 .env + 装 16 skills + 装 plugin + enable plugin
# → 自动写 state.json (deliver.target=feishu 或 weixin)
# → 起 adapter (retry-safe)
# → echo "✓ 全部完成。最后一步你自己终端跑：hermes gateway restart"
hermes gateway restart  # 用户手动
# → gateway 加载 plugin + skill → 16 skills enabled + 4 cron jobs + miloco_im_push 可用
```

跑完 `miloco_im_push "测试"` 应该立刻 `{"ok": true, ...}`，不需要任何 agent 手动修补。

---

## 给另一个 AI 的话

- 每个 issue 都标了 **修在哪**（具体文件 + 函数 / 节）和 **改法**（具体写法），照着做即可
- 改完跑 `pytest plugins/hermes/tests/` + `bash plugins/hermes/tests/test_install_e2e.sh`，预期 41 + 22 全过
- 改完顺手 `npx prettier --write plugins/hermes/` 跟格式
- 不要 commit / push，除非用户明确说"提交"
