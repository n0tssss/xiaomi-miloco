"""OpenAICompatibleProvider 行为契约测试。

v3 修订: provider 决定 video/audio block 形态。PR1 的 OpenAI 兼容 provider
需要跟原 hardcode 行为 1:1 对齐 (regression net)。

涵盖:
- video_block 形态: video_url + fps + media_resolution
- audio_block 形态: input_audio + data URL
- audio_block 接收空串返回 None (call site skip)
- request_kwargs 返回 {} (无 provider-specific override)
- supports_audio_only / merge_audio_into_video 旗标
- matches_url 永远 True (Layer 3 fallback)
"""

from miloco.perception.engine.providers import (
    OpenAICompatibleProvider,
    get_provider,
)


def test_video_block_returns_openai_wire_format():
    p = OpenAICompatibleProvider()
    block = p.video_block(video_b64="aGVsbG8=", fps=3)
    assert block == {
        "type": "video_url",
        "video_url": {"url": "data:video/mp4;base64,aGVsbG8="},
        "fps": 3,
        "media_resolution": "max",
    }


def test_video_block_ignores_audio_b64_kwarg():
    """OpenAI 有独立 input_audio 通道, video_block 收到 audio_b64 也丢弃。

    这是行为契约: PR2 的 MiniMax provider 会用 audio_b64 ffmpeg mux,
    OpenAI 兼容 provider 永远 ignore, 保持 wire format 不变。
    """
    p = OpenAICompatibleProvider()
    block = p.video_block(
        video_b64="AAAA", fps=5, audio_b64="BBBB", audio_sample_rate=16000
    )
    assert "video_url" in block
    assert "BBBB" not in str(block)  # audio 没塞进 video block


def test_video_block_returns_none_when_video_b64_none():
    p = OpenAICompatibleProvider()
    assert p.video_block(video_b64=None, fps=3) is None


def test_video_block_returns_none_for_empty_string():
    p = OpenAICompatibleProvider()
    # empty string 也是 falsy, provider 不构造空 data URL
    assert p.video_block(video_b64="", fps=3) is None


def test_video_block_data_url_prefix():
    p = OpenAICompatibleProvider()
    block = p.video_block(video_b64="dmlkZW8=", fps=2)
    url = block["video_url"]["url"]
    assert url.startswith("data:video/mp4;base64,")
    assert url.endswith("dmlkZW8=")


def test_audio_block_returns_input_audio_format():
    p = OpenAICompatibleProvider()
    block = p.audio_block(audio_b64="YXVkaW8=", sample_rate=16000)
    assert block == {
        "type": "input_audio",
        "input_audio": {"data": "data:audio/m4a;base64,YXVkaW8="},
    }


def test_audio_block_returns_none_for_empty_b64():
    p = OpenAICompatibleProvider()
    # PR1 行为契约: 短串 / 空串 → None, caller 跳过 audio block
    # 这跟 omni_client.py 原 hardcode 行为一致 (skip empty audio)
    assert p.audio_block(audio_b64="", sample_rate=16000) is None


def test_supports_audio_only_true():
    """OpenAI 有独立 input_audio 通道, 允许纯音频路由 (无视频)"""
    p = OpenAICompatibleProvider()
    assert p.supports_audio_only() is True


def test_merge_audio_into_video_false():
    """OpenAI 不需要 ffmpeg mux, audio 走独立 input_audio 通道"""
    p = OpenAICompatibleProvider()
    assert p.merge_audio_into_video() is False


def test_request_kwargs_empty_for_openai():
    """OpenAI 兼容 provider 无需额外 envelope 字段,request_kwargs 返 {}。

    max_tokens / temperature / top_p / stream 这些标准 envelope 由 caller
    直接 set(走 user config)。Provider 只在 model-specific envelope 字段
    (MiniMax 的 thinking 块、某些 stream_options 等)上需要返 dict。audio/video
    mux 等 wire-format 行为由 video_block() / audio_block() /
    merge_audio_into_video() 各自定义,跟 request_kwargs 无关。
    """
    p = OpenAICompatibleProvider()
    assert p.request_kwargs({"foo": "bar"}, fps=3) == {}


def test_matches_url_always_true():
    """OpenAI 兼容 provider 是 Layer 3 fallback, 认所有 URL"""
    p = OpenAICompatibleProvider()
    assert p.matches_url("https://api.openai.com/v1") is True
    assert p.matches_url("https://example.com/v1") is True
    assert p.matches_url("") is True


def test_name_attribute():
    p = OpenAICompatibleProvider()
    assert p.name == "openai"


def test_get_provider_returns_openai_for_explicit_declaration():
    p = get_provider("https://api.openai.com/v1", declared="openai")
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.name == "openai"
