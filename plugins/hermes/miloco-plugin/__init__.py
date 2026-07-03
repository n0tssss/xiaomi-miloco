"""Miloco for Hermes Agent —— 出站核心插件。

把 miloco（家庭智能管家）的能力以 Hermes 插件形式接入：

- **【hermes-pr.md §五 #2 迁移后】** 不再走 ``pre_llm_call`` 钩子(user message 注入,
  不命中 cache)。prompt 注入改由 backend 侧 ``AgentPlatformAdapter`` 加载 plugin 的
  ``HermesAdapter``,从 OpenAI ``<system>`` 消息注入(缓存友好)。
  Plugin 端 ``context_injection.py`` 保留 ``_build_prepend`` / ``_build_append`` 等
  静态 / 动态块构造函数,``install-hermes.sh`` Step 4.8 把 ``context_injection.py``
  副本 cp 到 ``$MILOCO_HOME/agent_platform/hermes/`` 给 Adapter import。
- 两个 tool: ``miloco_im_push``(通知投递, 对齐 OpenClaw 版
  ``subagent.run({deliver:true})`` 体验: 装好就能用, cron 场景下也能直接
  投递)、``miloco_habit_suggest``(习惯建议防骚扰状态机, 移植自
  ``home-profile/suggestions.ts``)。
- 启动时 reconcile 4 个受管 cron job(移植自 ``home-profile/scheduler.ts``)。

移植的 openclaw TS 源(逻辑 1:1):
- ``plugins/openclaw/src/miloco/paths.ts``       → paths.py
- ``plugins/openclaw/src/miloco/config.ts``      → config.py(读部分)
- ``plugins/openclaw/src/services/catalog.ts``   → catalog.py
- ``plugins/openclaw/src/hooks/prompt.ts``       → context_injection.py(只保留块构造, 无 pre_llm_call)
- ``plugins/openclaw/src/home-profile/helpers.ts`` → context_injection.py
- ``plugins/openclaw/src/home-profile/injection.ts`` → context_injection.py
- ``plugins/openclaw/src/tools/notify.ts``       → tools_notify.py
- ``plugins/openclaw/src/home-profile/suggestions.ts`` → tools_habit.py
- ``plugins/openclaw/src/home-profile/scheduler.ts`` → cron_setup.py

约束: Python 3.11+, 标准库 + httpx(Hermes 依赖里已有)。所有调 Hermes ctx 的地方
try/except, 插件加载不能因某个注册失败而崩。
"""

from __future__ import annotations

import logging

# 不再 import inject_context —— pre_llm_call 钩子已删(hermes-pr.md §五 #2)。
# context_injection 模块的 _build_prepend / _build_append / resolve_profile 等
# 函数仍被 install-hermes.sh Step 4.8 cp 到 $MILOCO_HOME/agent_platform/hermes/
# 给 HermesAdapter.build_system import。
#
# 【hermes-pr.md §五 #3 裁 tool】删 miloco_status / miloco_test_push 自检/调试工具:
#   - miloco_status: PR #279 时代调试用(诊断 7 项不变量),新架构下 `--diagnose`
#     自带同等覆盖(plugin 不再独立暴露),避免重复。
#   - miloco_test_push: 调试用,生产 agent 走 miloco_im_push 即可。
# 保留 im_push / habit_suggest / notify_bind 3 个 tool。
from .cron_setup import reconcile_cron_jobs
from .trace import register_trace_hooks
from .tools_habit import (
    MILOCO_HABIT_SUGGEST_SCHEMA,
    handle_habit_suggest,
)
from .tools_notify import (
    MILOCO_IM_PUSH_SCHEMA,
    make_im_push_handler,
)
from .tools_status import (
    MILOCO_NOTIFY_BIND_SCHEMA,
    handle_notify_bind,
)

logger = logging.getLogger(__name__)

TOOLSET = "miloco"


def register(ctx) -> None:
    """注册 trace hooks + 3 个 tool, 并 reconcile 受管 cron。

    【hermes-pr.md §五 #2 迁移后】删 ``pre_llm_call`` 注册 —— prompt 注入改走 backend
    HermesAdapter + OpenAI ``<system>`` 通路。这里只保留工具 / trace / cron 三类。

    【hermes-pr.md §五 #8 迁移后】register 触发 miloco backend 启动(原本由
    install-hermes.sh 负责;新架构下 plugin 启动应保证 backend 在线, 否则
    cron / trace / tool 都没 backend 可调)。``miloco-cli service restart`` 是幂等 +
    超时可控,且不影响 hermes gateway 进程组。

    每个注册独立 try/except: 单个失败不影响其余功能, 也绝不让插件加载崩掉 Hermes。
    """
    # ── 【hermes-pr.md §五 #8】register 触发 miloco backend 启动 ─────────────
    # 幂等: backend 已跑 → restart 是 no-op(service status 报告 running 即跳过)
    try:
        import shutil
        import subprocess
        if shutil.which("miloco-cli"):
            result = subprocess.run(
                ["miloco-cli", "service", "restart"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                logger.info("[miloco-backend] register 触发 backend restart: ok")
            else:
                logger.warning(
                    "[miloco-backend] register 触发 restart 失败 rc=%s stderr=%s",
                    result.returncode, (result.stderr or "")[:200],
                )
        else:
            logger.warning("[miloco-backend] miloco-cli 不在 PATH,跳过 register 拉后端")
    except subprocess.TimeoutExpired:
        logger.warning("[miloco-backend] register 触发 restart 超时(30s)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[miloco-backend] register 触发 restart 异常: %s", exc)

    # ── trace hooks(6 事件: pre/post_llm_call + pre/post_tool_call + on_session_start/end) ──
    # 对齐 OpenClaw trace.ts: debug 模式写 $MILOCO_HOME/trace/agent/<date>/*.jsonl.gz + .meta.json
    # 【hermes-pr.md §五 #11 迁移后】应改为常写(去掉 debug 门槛),backend HermesAdapter.read_trace_meta 读盘
    # —— 本 session 暂未实现 #11,保留 debug gate 让原有 trace webhook (plugin/adapter/) 通路继续工作。
    try:
        n = register_trace_hooks(ctx)
        logger.info("[miloco-trace] 已注册 %d 个 trace hooks", n)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[miloco-trace] 注册失败: %s", exc)

    # ── tools ──────────────────────────────────────────────────────────
    try:
        ctx.register_tool(
            name="miloco_im_push",
            toolset=TOOLSET,
            schema=MILOCO_IM_PUSH_SCHEMA,
            handler=make_im_push_handler(ctx),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("注册 miloco_im_push 失败: %s", exc)

    try:
        ctx.register_tool(
            name="miloco_habit_suggest",
            toolset=TOOLSET,
            schema=MILOCO_HABIT_SUGGEST_SCHEMA,
            handler=handle_habit_suggest,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("注册 miloco_habit_suggest 失败: %s", exc)

    # ── IM 切换 ──
    try:
        ctx.register_tool(
            name="miloco_notify_bind",
            toolset=TOOLSET,
            schema=MILOCO_NOTIFY_BIND_SCHEMA,
            handler=lambda args, **kw: handle_notify_bind(args, ctx),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("注册 miloco_notify_bind 失败: %s", exc)

    # ── 受管 cron reconcile ────────────────────────────────────────────
    # 放最后: cron 模块不在时 graceful 跳过, 不影响已注册的 hook/tool。
    try:
        result = reconcile_cron_jobs()
        if result.get("skipped"):
            logger.info("miloco cron reconcile 跳过(cron 模块不可用)")
        else:
            logger.info(
                "miloco cron reconcile 完成: created=%s updated=%s removed=%s",
                result.get("created"), result.get("updated"), result.get("removed"),
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("miloco cron reconcile 失败: %s", exc)
