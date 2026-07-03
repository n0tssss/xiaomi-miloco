"""pre_llm_call 上下文注入：profile 分级与文本块装配。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from miloco_plugin_pkg import context_injection as ci


@pytest.fixture
def tmp_miloco_home(tmp_path, monkeypatch):
    """临时 MILOCO_HOME，隔离真实配置。"""
    monkeypatch.setenv("MILOCO_HOME", str(tmp_path))
    return tmp_path


# ---------- resolve_profile ----------

def test_profile_cron(tmp_miloco_home):
    assert ci.resolve_profile("anything", platform="cron") == "minimal"
    assert ci.resolve_profile("miloco:cron:perception-digest") == "minimal"
    assert ci.resolve_profile("cron:foo") == "minimal"
    assert ci.resolve_profile("s", user_message="[cron:habit-suggest]") == "minimal"


def test_profile_rule_and_suggestion(tmp_miloco_home):
    assert ci.resolve_profile("miloco-rule-abc") == "rule"
    assert ci.resolve_profile("miloco-suggest-xyz") == "suggestion"


def test_profile_full(tmp_miloco_home):
    assert ci.resolve_profile("agent:main:miloco") == "full"
    assert ci.resolve_profile("anything-else") == "full"


# ---------- inject_context ----------

def test_full_includes_catalog_and_capabilities(tmp_miloco_home, monkeypatch):
    monkeypatch.setattr(ci, "get_catalog", lambda: "# devices catalog\n灯|客厅|light|online")
    out = ci.inject_context(session_id="agent:main:miloco", user_message="把客厅灯打开")
    assert out is not None
    ctx = out["context"]
    # 静态块: 071931f 改后只保留"工具索引"(被动清单),identity/notify/language
    # 这些指令性块改 "" 避免污染 user message(对齐 hermes-pr.md §五 #2)。
    # full profile 仍含"## 工具索引(被动清单)" + 感知格式 + 数据源 + 档案 + 目录。
    assert "## 工具索引(被动清单)" in ctx
    assert "miloco-devices" in ctx  # 工具清单内容
    # 数据块
    assert "# devices catalog" in ctx
    assert "## 家庭档案" in ctx  # profile.md 缺失时哨兵串仍带标题


def test_minimal_excludes_catalog_and_capabilities(tmp_miloco_home, monkeypatch):
    monkeypatch.setattr(ci, "get_catalog", lambda: "# devices catalog\nx")
    out = ci.inject_context(session_id="miloco:cron:digest", platform="cron")
    assert out is not None
    ctx = out["context"]
    # minimal 不附工具索引、感知格式、目录
    assert "## 工具索引(被动清单)" not in ctx
    assert "# devices catalog" not in ctx
    # minimal 仍可有感知格式(rule 也要)
    # 但 minimal 的"感知格式"块也省略(对齐 _build_prepend minimal 分支)
    assert "voice" not in ctx or "[感知引擎]语音提醒" not in ctx


def test_empty_catalog_omitted(tmp_miloco_home, monkeypatch):
    monkeypatch.setattr(ci, "get_catalog", lambda: "")
    out = ci.inject_context(session_id="agent:main", user_message="hi")
    assert out is not None
    assert "# devices catalog" not in out["context"]


def test_returns_none_when_nothing_to_inject(tmp_miloco_home, monkeypatch):
    # 071931f 后 identity/capabilities/notify/language 块均已对齐"事实陈述",
    # 即便 minimal + 无 catalog + 无 profile,prepend 还有数据源 + 感知格式子集
    # → inject_context 始终非 None。
    out = ci.inject_context(session_id="x", platform="cron")
    assert out is not None


# ---------- build_home_profile_block ----------

def test_home_profile_demotes_headings(tmp_miloco_home):
    prof = tmp_miloco_home / "home-profile" / "profile.md"
    prof.parent.mkdir(parents=True)
    prof.write_text("# 家庭档案\n爸爸喜欢 25 度\n## 作息\n早起", encoding="utf-8")
    block = ci.build_home_profile_block()
    assert "## 家庭档案" in block
    # 原 H1 降为 H2（与已有的 "## 家庭档案" 合流），原 H2 降为 H3
    assert "### 作息" in block
    assert "\n# 家庭档案" not in block  # 不应残留独立 H1


def test_home_profile_missing_sentinel(tmp_miloco_home):
    # 无 profile.md → load 层返回哨兵串 (暂无内容)，build 层补上标题后返回
    block = ci.build_home_profile_block()
    assert block == "## 家庭档案\n\n(暂无内容)"


# ---------- 异常安全 ----------

def test_inject_never_raises(tmp_miloco_home, monkeypatch):
    def boom():
        raise RuntimeError("catalog blew up")
    monkeypatch.setattr(ci, "get_catalog", boom)
    out = ci.inject_context(session_id="agent:main")
    # 钩子绝不抛：catalog 异常时应降级返回（仍含指令块）或 None，不能上抛
    assert out is None or "context" in out
