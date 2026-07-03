"""miloco IM 渠道管理工具。

【hermes-pr.md §五 #3 迁移后】只保留 notify_bind:
- ``miloco_notify_bind`` — IM 渠道切换:list 列出 state.json::candidates + 当前
  选中的;switch 切换 target。无需手动编辑 state.json。

PR #279 时代的 ``miloco_status`` / ``miloco_test_push`` 已删除:
  - 自检改由 ``bash plugins/hermes/install-hermes.sh --diagnose`` 提供
    (system 工具,不走 plugin tool 路径,用户和 agent 都能用)
  - test_push 改由 agent 直接调 miloco_im_push(自动同步 state.json target)

仅依赖 stdlib + 同包 tools_notify.load_state/save_state。
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import tools_notify as tn
from .paths import miloco_home

logger = logging.getLogger(__name__)

# 受管 cron job 期望名(供其他模块 / 未来 status 工具复用)
EXPECTED_CRON_NAMES = (
    "miloco-perception-digest",
    "miloco-home-patrol",
    "miloco-home-dreaming",
    "miloco-habit-suggest",
)


# ---------------------------------------------------------------------------
# candidates 检测(扫描 ~/.hermes/auth.json + config.yaml)
# ---------------------------------------------------------------------------


def _detect_im_platforms() -> List[str]:
    """扫描 hermes 配置:列出已配 bot_token 的 IM platform。

    与 install-hermes.sh Step 4.5 的 detect_im_platforms.py 行为对齐(简化版,
    这里只取 platform 名),供 list_candidates 用。
    """
    candidates: List[str] = []
    auth_path = Path.home() / ".hermes" / "auth.json"
    if auth_path.is_file():
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(auth, dict):
                for platform, conf in auth.items():
                    if isinstance(conf, dict) and conf.get("bot_token"):
                        candidates.append(platform)
        except (OSError, json.JSONDecodeError):
            pass
    cfg_path = Path.home() / ".hermes" / "config.yaml"
    if cfg_path.is_file():
        try:
            text = cfg_path.read_text(encoding="utf-8")
            # 简易扫描 platform: { ... bot_token: ... } 块
            import re
            for m in re.finditer(
                r"^(\w+):\s*\n(?:\s+.+\n)*?\s+bot_token:", text, re.MULTILINE,
            ):
                plat = m.group(1)
                if plat not in candidates and plat not in ("platforms", "gateway", "model", "plugins"):
                    candidates.append(plat)
        except OSError:
            pass
    return candidates


def _get_hermes_version() -> str:
    """读 hermes --version,失败返 unknown。"""
    if not shutil.which("hermes"):
        return "unknown"
    try:
        r = subprocess.run(
            ["hermes", "--version"], capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            lines = (r.stdout or r.stderr or "").strip().splitlines()
            return lines[0] if lines else "empty-output"
        return f"err:{r.returncode}"
    except Exception as exc:  # noqa: BLE001
        return f"err:{exc}"


def _get_miloco_cli_version() -> str:
    """读 miloco-cli version。"""
    if not shutil.which("miloco-cli"):
        return "unknown"
    try:
        r = subprocess.run(
            ["miloco-cli", "version"], capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            raw = (r.stdout or "").strip()
            if raw.startswith("{"):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and "version" in parsed:
                        return parsed["version"]
                except json.JSONDecodeError:
                    pass
            return raw.splitlines()[0] if raw else "empty-output"
        return f"err:{r.returncode}"
    except Exception as exc:  # noqa: BLE001
        return f"err:{exc}"


def _get_plugin_version(ctx: Any) -> str:
    """从装好的 plugin.yaml 读 plugin 版本。"""
    try:
        import os as _os
        manifest_base = getattr(getattr(ctx, "manifest", None), "path", "")
        candidates = []
        if manifest_base and Path(manifest_base).is_dir():
            candidates.append(Path(manifest_base) / "plugin.yaml")
        hermes_home = Path(_os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
        candidates.append(
            hermes_home / "plugins" / "miloco" / "miloco-plugin" / "plugin.yaml"
        )
        for plugin_yaml in candidates:
            if plugin_yaml.is_file():
                for line in plugin_yaml.read_text(encoding="utf-8").splitlines():
                    if line.startswith("version:"):
                        return line.split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# miloco_notify_bind
# ---------------------------------------------------------------------------


def list_candidates(ctx: Any) -> Dict[str, Any]:
    """列 state.json::candidates + 当前 target(标 ✓)。"""
    state = tn.load_state(ctx)
    deliver = state.get("deliver") or {}
    candidates = deliver.get("candidates") or []
    current = deliver.get("target")
    if not candidates:
        # fallback:实时扫 ~/.hermes 给 agent 提供当前可用候选
        candidates = _detect_im_platforms()
    return {
        "ok": True,
        "current": current,
        "auto_configured": deliver.get("auto_configured"),
        "candidates": candidates,
        "candidates_count": len(candidates),
        "hint": (
            "candidates 为空 → install-hermes.sh 装时没读到任何 IM。"
            "在 Hermes 里连 IM(hermes config set feishu.app_id ...)后重跑 install-hermes.sh,"
            "或直接 miloco_notify_bind(action='switch', target='feishu') 临时设。"
        ),
    }


def switch_target(ctx: Any, target: str) -> Dict[str, Any]:
    """切换 deliver.target(覆盖 auto_configured 标记,标 source=manual)。"""
    target = (target or "").strip()
    if not target:
        return {"ok": False, "error": "target 不能为空"}
    state = tn.load_state(ctx)
    state["deliver"] = {
        "target": target,
        "auto_configured": False,
        "configured_at": datetime.now().astimezone().isoformat(),
        "source": "manual via miloco_notify_bind",
        "candidates": (state.get("deliver") or {}).get("candidates") or [],
    }
    tn.save_state(ctx, state)
    return {"ok": True, "target": target, "note": "已切换;下次 miloco_im_push 会用新 target"}


def gather_versions(ctx: Any) -> Dict[str, Any]:
    """读 state.json::versions 与当前系统版本对比 — 升级一致性检查。

    【hermes-pr.md §五 #3 迁移后】这是 PR #279 miloco_status 的子集提取,
    仅保留 version diff 检查 — 其他 6 项被 install-hermes.sh --diagnose 覆盖。
    """
    state = tn.load_state(ctx)
    recorded = state.get("versions") or {}
    cur = {
        "hermes": _get_hermes_version(),
        "miloco_cli": _get_miloco_cli_version(),
        "plugin": _get_plugin_version(ctx),
    }
    mismatches = []
    for key in ("hermes", "miloco_cli", "plugin"):
        rec = recorded.get(key, "")
        c = cur[key]
        if rec and rec != "unknown" and c != "unknown" and c != rec:
            mismatches.append(f"{key}: 装时={rec} 现在={c}")
    return {
        "ok": len(mismatches) == 0,
        "current": cur,
        "recorded": recorded,
        "mismatches": mismatches,
        "fix": (
            "重跑 bash plugins/hermes/install-hermes.sh 更新 versions;"
            "若只 hermes 变了,hermes gateway restart 即可(plugin 端自动重载)"
        ) if mismatches else None,
    }


# ---------------------------------------------------------------------------
# tool schema + handler
# ---------------------------------------------------------------------------


MILOCO_NOTIFY_BIND_SCHEMA: Dict[str, Any] = {
    "name": "miloco_notify_bind",
    "description": (
        "IM 渠道管理:list 候选 / switch 切换 / versions 检查(升级一致性)。\n"
        "action='list':列 state.json 里 install-hermes.sh 探测到的所有候选 + 当前 target。"
        "返回 candidates 数组,每个元素是 hermes send 接受的 target 串(如 'feishu:oc_xxx:om_xxx')。\n"
        "action='switch':覆盖当前 target,标 source=manual。target 必须是 hermes send 接受的格式\n"
        "('platform' 或 'platform:chat_id' 或 'platform:chat_id:thread_id')。\n"
        "action='versions':对比 state.json::versions 与当前系统版本(升级一致性检查)。\n"
        "**无需重启 hermes**——下次 miloco_im_push 自动用新 target。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "switch", "versions"],
                "description": "操作:list 候选 / switch 切换 / versions 检查",
            },
            "target": {
                "type": "string",
                "description": "switch 的目标 target(如 'feishu' 或 'feishu:oc_xxx')",
            },
        },
        "required": ["action"],
    },
}


def handle_notify_bind(args: Dict[str, Any], ctx: Any) -> str:
    """``miloco_notify_bind`` handler(ctx 由 __init__.py 闭包注入)。

    不用 ``**kwargs`` 是因为 hermes 的 tool 注册签名通常显式传 ctx;
    为兼容各种 hermes 版本,把 ctx 显式作为第二参数。
    """
    args = args if isinstance(args, dict) else {}
    action = (args.get("action") or "").strip()
    try:
        if action == "list":
            result = list_candidates(ctx)
        elif action == "switch":
            result = switch_target(ctx, args.get("target", ""))
        elif action == "versions":
            result = gather_versions(ctx)
        else:
            result = {
                "ok": False,
                "error": f"未知 action:{action!r}(应为 list / switch / versions)",
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("miloco_notify_bind 失败: %s", exc)
        result = {"ok": False, "error": f"internal error: {exc}"}
    return json.dumps(result, ensure_ascii=False)