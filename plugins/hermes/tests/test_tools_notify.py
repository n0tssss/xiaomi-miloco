"""miloco_im_push 工具：state.json 投递 + 无 target 时的明确错误。

新流程（v0.2.0）：安装时 install-hermes.sh 自动探测 Hermes IM 平台写入
state.json::deliver.target，运行时直接调 ``ctx.dispatch_tool("send_message", ...)``。
不再做两段式 bind——cron session 没人可对话，bind 走不通。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from miloco_plugin_pkg import tools_notify as tn


# ---------- fake ctx ----------

class _FakeCtx:
    """最小 Hermes ctx 替身：只暴露 manifest.path + dispatch_tool。"""

    def __init__(self, plugin_dir: Path, send_message_result: Any = None):
        self.manifest = type("M", (), {"path": str(plugin_dir)})()
        self._send_message_result = send_message_result
        self.calls: list[Dict[str, Any]] = []

    def dispatch_tool(self, name: str, args: Dict[str, Any]) -> str:
        self.calls.append({"name": name, "args": args})
        if name != "send_message":
            return json.dumps({"error": f"unexpected tool {name}"})
        if isinstance(self._send_message_result, Exception):
            raise self._send_message_result
        if isinstance(self._send_message_result, str):
            return self._send_message_result
        return json.dumps(self._send_message_result or {"success": True, "platform": "telegram"})


# ---------- state.json 读写 ----------

def test_state_roundtrip(tmp_path: Path):
    state_file = tmp_path / "state.json"
    ctx = _FakeCtx(tmp_path)
    assert tn.get_deliver_target(ctx) is None

    tn.set_deliver_target(ctx, "telegram:-1001234567890:17585")
    assert state_file.is_file()
    assert tn.get_deliver_target(ctx) == "telegram:-1001234567890:17585"

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["deliver"]["target"] == "telegram:-1001234567890:17585"
    assert payload["deliver"]["auto_configured"] is False


def test_state_corrupt_returns_empty(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("not json {", encoding="utf-8")
    ctx = _FakeCtx(tmp_path)
    assert tn.get_deliver_target(ctx) is None  # 损坏不抛，返回 None


def test_state_missing_returns_empty(tmp_path: Path):
    ctx = _FakeCtx(tmp_path)  # state.json 不存在
    assert tn.get_deliver_target(ctx) is None


def test_state_with_deliver_key_but_no_target(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"deliver": {"auto_configured": True}}), encoding="utf-8")
    ctx = _FakeCtx(tmp_path)
    assert tn.get_deliver_target(ctx) is None  # target 缺失视同未配


# ---------- notify_owner 投递 ----------

def test_notify_no_target_returns_clear_error(tmp_path: Path):
    ctx = _FakeCtx(tmp_path)  # 无 state.json
    result = tn.notify_owner(ctx, "hello")
    assert result["ok"] is False
    assert "no deliver target configured" in result["error"]
    assert ctx.calls == []  # 没调 send_message


def test_notify_success(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"deliver": {"target": "telegram"}}), encoding="utf-8"
    )
    ctx = _FakeCtx(tmp_path, send_message_result={
        "success": True, "platform": "telegram", "chat_id": "-100xxx"
    })
    result = tn.notify_owner(ctx, "喝水提醒")
    assert result == {"ok": True, "platform": "telegram", "chat_id": "-100xxx"}
    assert len(ctx.calls) == 1
    assert ctx.calls[0]["name"] == "send_message"
    assert ctx.calls[0]["args"]["target"] == "telegram"
    assert "<miloco-notification>" in ctx.calls[0]["args"]["message"]
    assert "喝水提醒" in ctx.calls[0]["args"]["message"]


def test_notify_with_chat_id_target(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"deliver": {"target": "telegram:-1001234567890:17585"}}),
        encoding="utf-8",
    )
    ctx = _FakeCtx(tmp_path, send_message_result={"success": True, "platform": "telegram"})
    tn.notify_owner(ctx, "x")
    assert ctx.calls[0]["args"]["target"] == "telegram:-1001234567890:17585"


def test_notify_send_message_error_propagates(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"deliver": {"target": "telegram"}}), encoding="utf-8")
    ctx = _FakeCtx(tmp_path, send_message_result={"success": False, "error": "no route"})
    result = tn.notify_owner(ctx, "x")
    assert result["ok"] is False
    assert "no route" in result["error"]


def test_notify_dispatch_tool_raises(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"deliver": {"target": "telegram"}}), encoding="utf-8")
    ctx = _FakeCtx(tmp_path, send_message_result=RuntimeError("dispatch blew up"))
    result = tn.notify_owner(ctx, "x")
    assert result["ok"] is False
    assert "dispatch_tool" in result["error"]


# ---------- handler 包装 ----------

def test_handler_empty_message(tmp_path: Path):
    ctx = _FakeCtx(tmp_path)
    handler = tn.make_im_push_handler(ctx)
    out = json.loads(handler({"message": ""}))
    assert out["ok"] is False
    assert "message" in out["error"]


def test_handler_no_state_json(tmp_path: Path):
    ctx = _FakeCtx(tmp_path)
    handler = tn.make_im_push_handler(ctx)
    out = json.loads(handler({"message": "hi"}))
    assert out["ok"] is False
    assert "no deliver target" in out["error"]


def test_handler_delivers(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"deliver": {"target": "telegram"}}), encoding="utf-8")
    ctx = _FakeCtx(tmp_path, send_message_result={"success": True, "platform": "telegram"})
    handler = tn.make_im_push_handler(ctx)
    out = json.loads(handler({"message": "fire alarm"}))
    assert out == {"ok": True, "platform": "telegram", "chat_id": None}