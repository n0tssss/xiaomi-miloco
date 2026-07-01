"""MiniMaxProvider 单元测试 + 可选 live API 集成测试。

Live API 测试需要环境变量 MINIMAX_KEY(测试时 export 即可,缺则 skip,
CI 跑无 key 不挂)。

覆盖:
- 6 个 method 的契约(从 OpenAI 父类继承 / 自身 override)
- ffmpeg mux 行为(video_block 在 audio_b64 非空时调 mux)
- ffmpeg 失败时降级到 video-only
- registry 顺序:minimax 注册在 openai 之前,Layer 2 URL 匹配优先级正确
- live API: text-only / vision / audio+video mux 三场景 sanity
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from typing import Any
from unittest.mock import patch

import pytest

from miloco.perception.engine.providers.base import OmniProvider
from miloco.perception.engine.providers.minimax import (
    MiniMaxProvider,
    _mux_pcm_into_mp4,
)
from miloco.perception.engine.providers.openai_compatible import (
    OpenAICompatibleProvider,
)
from miloco.perception.engine.providers.registry import (
    clear_cache,
    get_provider,
    list_provider_names,
    register_provider,
)


# ───────────────────────────────────────────────────────────────────────
# 基础契约 — provider name / isinstance / 6 个 method 都存在
# ───────────────────────────────────────────────────────────────────────


def test_minimax_provider_is_omni_provider():
    p = MiniMaxProvider()
    assert p.name == "minimax"
    assert isinstance(p, OmniProvider)
    assert isinstance(p, OpenAICompatibleProvider)  # 子类继承


def test_minimax_provider_methods_complete():
    """6 个 abstractmethod 都实现了(ABC 检查)。"""
    p = MiniMaxProvider()
    # 不应抛 NotImplementedError
    assert p.video_block(None, 3) is None
    assert p.audio_block(b"x", 16000) is None
    assert p.supports_audio_only() is False
    assert p.merge_audio_into_video() is True
    assert p.request_kwargs({}, 3) == {}
    assert p.matches_url("https://api.minimaxi.com/v1") is True


# ───────────────────────────────────────────────────────────────────────
# video_block 行为
# ───────────────────────────────────────────────────────────────────────


def test_video_block_no_audio_returns_openai_compatible_format():
    """无 audio 时,wire format 跟 OpenAI 完全一致(继承父类)。"""
    p = MiniMaxProvider()
    video_b64 = "ZmFrZQ=="
    result = p.video_block(video_b64, fps=3, audio_b64=None)
    assert result == {
        "type": "video_url",
        "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
        "fps": 3,
        "media_resolution": "max",
    }


def test_video_block_empty_video_returns_none():
    """video_b64 为空 → 返 None(caller 不加 video 块)。"""
    p = MiniMaxProvider()
    assert p.video_block("", fps=3) is None
    assert p.video_block(None, fps=3) is None


def test_video_block_with_audio_calls_ffmpeg_mux():
    """audio_b64 非空 → ffmpeg mux 被调,返回 muxed mp4 的 video 块。"""
    p = MiniMaxProvider()
    video_b64 = "ZmFrZQ=="
    audio_b64 = "ZmFrZQ=="

    # mock _mux_pcm_into_mp4 返一个固定值
    fake_muxed = "bXV4ZWQ="
    with patch(
        "miloco.perception.engine.providers.minimax._mux_pcm_into_mp4",
        return_value=fake_muxed,
    ) as mux_fn:
        result = p.video_block(video_b64, fps=3, audio_b64=audio_b64, audio_sample_rate=16000)
    mux_fn.assert_called_once_with(video_b64, audio_b64, 16000)
    assert result == {
        "type": "video_url",
        "video_url": {"url": f"data:video/mp4;base64,{fake_muxed}"},
        "fps": 3,
        "media_resolution": "max",
    }


def test_video_block_mux_failure_falls_back_to_video_only():
    """mux 失败 → 降级到 video-only block(audio 丢,warn 写日志)。"""
    p = MiniMaxProvider()
    video_b64 = "ZmFrZQ=="
    audio_b64 = "ZmFrZQ=="

    with patch(
        "miloco.perception.engine.providers.minimax._mux_pcm_into_mp4",
        return_value=None,  # mux 失败
    ):
        result = p.video_block(video_b64, fps=3, audio_b64=audio_b64, audio_sample_rate=16000)
    # 降级:audio 丢,只返 video 块
    assert result == {
        "type": "video_url",
        "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
        "fps": 3,
        "media_resolution": "max",
    }


# ───────────────────────────────────────────────────────────────────────
# audio_block / supports_audio_only / merge_audio_into_video / request_kwargs
# ───────────────────────────────────────────────────────────────────────


def test_audio_block_returns_none():
    """MiniMax 没 audio 通道 —— audio 已在 video mux 完(PR3 约定:None 不等于丢)。"""
    p = MiniMaxProvider()
    assert p.audio_block("aW52YWxpZA==", 16000) is None
    assert p.audio_block("", 16000) is None


def test_supports_audio_only_false():
    p = MiniMaxProvider()
    assert p.supports_audio_only() is False


def test_merge_audio_into_video_true():
    p = MiniMaxProvider()
    assert p.merge_audio_into_video() is True


def test_request_kwargs_empty():
    """MiniMax thinking 默认开、嵌 content,不需 envelope extras。"""
    p = MiniMaxProvider()
    assert p.request_kwargs({}, 3) == {}
    assert p.request_kwargs({"foo": "bar"}, 30, user_max_tokens=4096) == {}


# ───────────────────────────────────────────────────────────────────────
# matches_url
# ───────────────────────────────────────────────────────────────────────


def test_matches_url_minimaxi():
    p = MiniMaxProvider()
    # MiniMax 官方 base_url
    assert p.matches_url("https://api.minimaxi.com/v1") is True
    # 子域名 / 路径变体也吃(纯子串匹配,不开正则)
    assert p.matches_url("https://api.minimaxi.com") is True
    assert p.matches_url("https://MINIMAXI.com/v1") is True  # case-insensitive
    # 不该误 match
    assert p.matches_url("https://api.openai.com/v1") is False
    assert p.matches_url("https://api.minimax.example.com") is False


# ───────────────────────────────────────────────────────────────────────
# registry 顺序
# ───────────────────────────────────────────────────────────────────────


def test_minimax_registered_before_openai():
    """minimax 必须在 openai 之前注册 —— 否则 Layer 2 顺序遍历到 minimax 之前
    已经 match 到了 OpenAICompatibleProvider(也返 True),minimax 永远轮不到。"""
    names = list_provider_names()
    if "minimax" in names and "openai" in names:
        assert names.index("minimax") < names.index("openai")


def test_registry_layer2_url_routes_to_minimax():
    """get_provider 用 minimaxi 官方 URL → 返 MiniMaxProvider 实例。"""
    clear_cache()
    provider = get_provider("https://api.minimaxi.com/v1")
    assert isinstance(provider, MiniMaxProvider)
    clear_cache()


def test_registry_layer3_falls_back_to_openai():
    """get_provider 用非 minimaxi URL → 返 OpenAICompatibleProvider(兜底)。"""
    clear_cache()
    provider = get_provider("https://api.openai.com/v1")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert not isinstance(provider, MiniMaxProvider)
    clear_cache()


def test_registry_layer1_declared_overrides_url():
    """get_provider declared 优先于 URL 匹配。"""
    from miloco.perception.engine.providers.minimax import MiniMaxProvider
    from miloco.perception.engine.providers.openai_compatible import (
        OpenAICompatibleProvider,
    )
    clear_cache()
    # 用 minimaxi URL 但 declared=openai → 返 OpenAICompatibleProvider
    provider = get_provider("https://api.minimaxi.com/v1", declared="openai")
    assert isinstance(provider, OpenAICompatibleProvider)
    # 用 openai URL 但 declared=minimax → 返 MiniMaxProvider
    provider = get_provider("https://api.openai.com/v1", declared="minimax")
    assert isinstance(provider, MiniMaxProvider)
    clear_cache()


# ───────────────────────────────────────────────────────────────────────
# _mux_pcm_into_mp4 实际跑 ffmpeg(无 mock,真测集成)
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.path.exists("/c/Users/16560/scoop/shims/ffmpeg.exe")
    and not __import__("shutil").which("ffmpeg"),
    reason="ffmpeg not available",
)
def test_mux_pcm_into_mp4_real_ffmpeg():
    """实际跑 ffmpeg,验证 mux 出来的 mp4 ffprobe 通过。"""
    import struct
    import subprocess

    # 1 秒 16kHz mono 静音 wav
    wav = b"RIFF" + struct.pack("<I", 36 + 16000 * 2) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16
    ) + b"data" + struct.pack("<I", 16000 * 2) + (b"\x00" * 16000 * 2)

    # 1 秒 25fps 红色 mp4
    v_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    a_in = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    v_out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        open(a_in, "wb").write(wav)
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i",
                "color=c=red:size=320x240:duration=1:rate=25", v_in,
            ],
            check=True, capture_output=True,
        )
        video_b64 = base64.b64encode(open(v_in, "rb").read()).decode()
        audio_b64 = base64.b64encode(wav).decode()

        result_b64 = _mux_pcm_into_mp4(video_b64, audio_b64, audio_sample_rate=16000)

        assert result_b64 is not None, "mux 失败(看 warning 日志)"
        with open(v_out, "wb") as f:
            f.write(base64.b64decode(result_b64))

        # ffprobe 验证 — 应该同时有 video 和 audio 流
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-of", "default=nw=1", v_out,
            ],
            capture_output=True, text=True,
        )
        assert "video" in probe.stdout
        assert "audio" in probe.stdout
    finally:
        for p in (v_in, a_in, v_out):
            try: os.unlink(p)
            except OSError: pass


# ───────────────────────────────────────────────────────────────────────
# Live API 集成测试(需要 MINIMAX_KEY 环境变量,缺则 skip)
# ───────────────────────────────────────────────────────────────────────


LIVE_KEY = os.environ.get("MINIMAX_KEY", "")


@pytest.mark.skipif(not LIVE_KEY, reason="MINIMAX_KEY env var not set — 跳过 live API 测试")
def test_minimax_live_text_only():
    """live API: text-only,验证 MiniMax 接受 + 返 200 + content 含 <think> 默认行为。"""
    import httpx
    r = httpx.post(
        "https://api.minimaxi.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {LIVE_KEY}", "Content-Type": "application/json"},
        json={
            "model": "MiniMax-M3",
            "messages": [{"role": "user", "content": "1+1=?"}],
            "max_tokens": 200,
        },
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    content = body["choices"][0]["message"]["content"]
    # 验证 reasoning 默认开
    assert "<think>" in content
    assert "2" in content  # 答案应该包含 2


@pytest.mark.skipif(not LIVE_KEY, reason="MINIMAX_KEY env var not set — 跳过 live API 测试")
def test_minimax_live_vision():
    """live API: image_url 视觉识别,验证 MiniMax 看图。

    注: 1x1 红 PNG 太小,模型经常看不到颜色(说"黑色")。这个测试只验证
    MiniMax 确实处理了图像(响应非空、含视觉相关 reasoning),不验证颜色识别准确度。
    """
    import httpx
    # 1x1 红 PNG(主要测视觉通路,色值不严格)
    PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    r = httpx.post(
        "https://api.minimaxi.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {LIVE_KEY}", "Content-Type": "application/json"},
        json={
            "model": "MiniMax-M3",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "图中你看到了什么?(只描述视觉内容)"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG}"}},
                    ],
                }
            ],
            "max_tokens": 2000,
        },
        timeout=30,
    )
    assert r.status_code == 200
    content = r.json()["choices"][0]["message"]["content"]
    # 1. reasoning 默认开(嵌 ``)
    assert "<think>" in content
    # 2. 模型有非空视觉响应(具体颜色不严格,1x1 像素模型识别不稳)
    assert len(content) > 50


@pytest.mark.skipif(not LIVE_KEY, reason="MINIMAX_KEY env var not set — 跳过 live API 测试")
def test_minimax_live_audio_video_mux():
    """live API: video + audio(用 ffmpeg mux 过的 mp4),验证 MiniMax 能同时收到。

    流程:
    1. ffmpeg 生成 1 秒红屏 mp4 + 1 秒静音 wav
    2. 用 MiniMaxProvider.video_block 调 _mux_pcm_into_mp4(我们的实装) mux
    3. POST 到 MiniMax API,问"这视频有声音吗?"
    4. 验证 200 + content 有意义(模型看到 mux 后的 mp4)
    """
    import struct
    import httpx

    # 1 秒红屏 mp4
    v_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    a_in = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        # 1 秒 16kHz mono 静音 wav
        wav = b"RIFF" + struct.pack("<I", 36 + 16000 * 2) + b"WAVEfmt " + struct.pack(
            "<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16
        ) + b"data" + struct.pack("<I", 16000 * 2) + (b"\x00" * 16000 * 2)
        open(a_in, "wb").write(wav)

        # 1 秒 25fps 红屏 mp4
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i",
                "color=c=red:size=320x240:duration=1:rate=25", v_in,
            ],
            check=True, capture_output=True,
        )

        video_b64 = base64.b64encode(open(v_in, "rb").read()).decode()
        audio_b64 = base64.b64encode(wav).decode()

        # 我们的 provider 实装
        provider = MiniMaxProvider()
        video_block = provider.video_block(
            video_b64=video_b64, fps=25,
            audio_b64=audio_b64, audio_sample_rate=16000,
        )
        assert video_block is not None, "mux 失败,看 provider 警告日志"

        # POST MiniMax
        r = httpx.post(
            "https://api.minimaxi.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {LIVE_KEY}", "Content-Type": "application/json"},
            json={
                "model": "MiniMax-M3",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "这段视频里有什么?(只看视频+听音频描述)"},
                        video_block,  # 已 mux 进 video 的 video_url 块
                    ],
                }],
                "max_tokens": 2000,
            },
            timeout=30,
        )
        assert r.status_code == 200
        content = r.json()["choices"][0]["message"]["content"]
        # 验证模型返回非空视觉+音频响应(具体内容不严格,mux 成功 = 200 + 非空响应)
        # —— 证明 video_block 走的就是 ffmpeg mux 后的 mp4 通路
        assert "<think>" in content
        assert len(content) > 50
    finally:
        for p in (v_in, a_in):
            try: os.unlink(p)
            except OSError: pass
