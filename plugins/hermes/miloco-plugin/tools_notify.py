"""miloco_im_push 通知投递。

对齐 OpenClaw 版 ``subagent.run({deliver:true})`` 的体验：装好就能用，cron
场景下也能自动投递，不需要 LLM 配合做"两段式 bind"。

**投递路径**：读插件 state.json 里的 ``deliver.target``（格式
``platform[:chat_id[:thread_id]]``，对齐 Hermes `send_message` 工具签名，见
``hermes-agent/tools/send_message_tool.py::SEND_MESSAGE_SCHEMA``），经
``ctx.dispatch_tool("send_message", {action, target, message})`` 投递。

**state.json 由 install-hermes.sh 在安装时自动写**：探测 ~/.hermes/config.yaml
里已配 bot_token 的 platform，取第一个作为默认 deliver target，用户零感知。
若未检测到任何已配平台，state.json 里无 deliver 字段，im_push 返回
``ok:false, error:"no deliver target configured"``，提示用户去 Hermes 里配 IM
或手动编辑 state.json。

**best-effort 标注**：投递失败仅 log + 返回 ok:false；send_message 工具签名从
Hermes v0.10.0 源码确认（见 ``tools/send_message_tool.py::_handle_send``），
未来 Hermes 改签名需相应调整。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# state.json 文件名（与 OpenClaw 版 notify.ts 对齐，存于插件根目录）
_STATE_FILENAME = "state.json"


def _state_path(ctx: Any) -> Path:
    """插件目录下的 state.json。ctx.manifest.path 是插件根目录。"""
    base = getattr(getattr(ctx, "manifest", None), "path", None)
    if not base:
        # 兜底：~/.hermes/plugins/miloco/state.json（极少走到）。
        base = str(Path.home() / ".hermes" / "plugins" / "miloco")
    return Path(base) / _STATE_FILENAME


def load_state(ctx: Any) -> Dict[str, Any]:
    """读 state.json，缺失/损坏返回空 dict。"""
    path = _state_path(ctx)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("miloco state.json 解析失败 (%s): %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_state(ctx: Any, state: Dict[str, Any]) -> None:
    """原子写 state.json（temp → rename）。失败仅 log，不抛。"""
    path = _state_path(ctx)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("miloco state.json 写入失败 (%s): %s", path, exc)


def get_deliver_target(ctx: Any) -> Optional[str]:
    """从 state.json 读 deliver.target；缺失返回 None。

    返回值是 Hermes ``send_message`` 工具接受的 target 字符串，格式
    ``platform[:chat_id[:thread_id]]``。裸 ``platform`` 表示用 home channel。
    """
    return load_state(ctx).get("deliver", {}).get("target") or None


def set_deliver_target(ctx: Any, target: str) -> None:
    """手动覆盖 deliver.target（高级用户用；正常路径 install-hermes.sh 自动写）。"""
    state = load_state(ctx)
    state["deliver"] = {
        "target": target,
        "auto_configured": False,
        "configured_at": None,
        "source": "manual set via plugin API",
    }
    save_state(ctx, state)


# ---------------------------------------------------------------------------
# 投递
# ---------------------------------------------------------------------------

def _deliver_via_send_message(ctx: Any, target: str, body: str) -> Dict[str, Any]:
    """经 Hermes ``send_message`` tool 投递。返回 ``{"ok": bool, "error": str?}``。

    ``send_message`` 工具签名（hermes-agent/tools/send_message_tool.py）：
      action ∈ {"send", "list"}（默认 "send"）
      target: "platform" 或 "platform:chat_id" 或 "platform:chat_id:thread_id"
      message: 文本
    返回 JSON 字符串：``{"success": bool, "error"?: str, "platform"?: str, ...}``。
    """
    try:
        result_str = ctx.dispatch_tool("send_message", {
            "action": "send",
            "target": target,
            "message": body,
        })
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"dispatch_tool(send_message) failed: {exc}"}

    try:
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": f"send_message returned non-JSON: {result_str!r}"}

    if not isinstance(result, dict):
        return {"ok": False, "error": f"unexpected send_message result: {result!r}"}
    if result.get("success") is True:
        return {"ok": True, "platform": result.get("platform"), "chat_id": result.get("chat_id")}
    return {"ok": False, "error": str(result.get("error") or result)}


def notify_owner(ctx: Any, message: str) -> Dict[str, Any]:
    """投递入口。与 OpenClaw 版 ``notifyOwner`` 行为对齐：装好就能用。

    没有 deliver target → 返回 ok:false + 明确错误，指引用户去装 IM 或手动
    编辑 state.json。不再做"两段式 bind"——cron session 没人可对话，bind 走
    不通。
    """
    target = get_deliver_target(ctx)
    if not target:
        return {
            "ok": False,
            "error": (
                "no deliver target configured. Run install-hermes.sh after connecting "
                "an IM platform in Hermes, or manually edit state.json "
                "(`{\"deliver\": {\"target\": \"telegram\"}}`)."
            ),
        }
    body = f"<miloco-notification>{message}</miloco-notification>"
    return _deliver_via_send_message(ctx, target, body)


# ---------------------------------------------------------------------------
# tool schema + handler 工厂
# ---------------------------------------------------------------------------

MILOCO_IM_PUSH_SCHEMA: Dict[str, Any] = {
    "name": "miloco_im_push",
    "description": (
        "给主人推送一条 IM 通知。通常只传 message 调用即可——通知会自动送到 "
        "install-hermes.sh 配置好的 IM 频道（无需 bind）。\n"
        "本工具配合 miloco-notify skill 使用（分级、选人、文案规范都在其中）。\n"
        "失败时返回 ok=false + error：常见原因是 Hermes 还没接 IM 平台，"
        "按 error 提示跑 hermes config set 或编辑 state.json 后重试。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "要发给主人的通知正文",
            },
        },
        "required": ["message"],
    },
}


def make_im_push_handler(ctx: Any):
    """返回 ``miloco_im_push`` 的 handler（闭包捕获 ctx）。"""
    def _handler(args: Dict[str, Any], **kwargs: Any) -> str:
        message = (args.get("message") or "").strip()
        if not message:
            return json.dumps({"ok": False, "error": "message 不能为空"}, ensure_ascii=False)
        try:
            result = notify_owner(ctx, message)
        except Exception as exc:  # noqa: BLE001
            logger.exception("miloco_im_push 失败: %s", exc)
            result = {"ok": False, "error": f"internal error: {exc}"}
        return json.dumps(result, ensure_ascii=False)
    return _handler