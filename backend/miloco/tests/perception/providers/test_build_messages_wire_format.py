"""_build_messages 接 provider 后的 wire format 回归测试。

PR1 必须行为不变: video block 跟原 hardcode 完全一致 (video_url + fps +
media_resolution), audio-only block 走 input_audio。这是 PR1 的 regression net
—— 如果未来 _build_messages 改动把 wire format 改了,这些测试要 fail。
"""

from miloco.perception.engine.omni.omni_client import _build_messages
from miloco.perception.engine.providers import OpenAICompatibleProvider


def test_build_messages_with_video_block():
    p = OpenAICompatibleProvider()
    messages = _build_messages(
        {
            "system_prompt": "You are a helpful assistant.",
            "user_content": "What do you see?",
            "video_base64": "dmlkZW9iNjQ=",
            "video_fps": 3,
        },
        p,
    )
    assert len(messages) == 2
    assert messages[0] == {
        "role": "system",
        "content": "You are a helpful assistant.",
    }
    user_content = messages[1]["content"]
    assert user_content[0] == {"type": "text", "text": "What do you see?"}
    # video block 跟原 hardcode 完全一致
    assert user_content[1] == {
        "type": "video_url",
        "video_url": {"url": "data:video/mp4;base64,dmlkZW9iNjQ="},
        "fps": 3,
        "media_resolution": "max",
    }


def test_build_messages_with_audio_only():
    p = OpenAICompatibleProvider()
    messages = _build_messages(
        {
            "system_prompt": "S",
            "user_content": "U",
            "video_base64": None,
            "audio_base64": "YXVkaW9iNjQ=",
        },
        p,
    )
    user_content = messages[1]["content"]
    # audio-only 路由走 input_audio 块
    assert user_content[1] == {
        "type": "input_audio",
        "input_audio": {"data": "data:audio/m4a;base64,YXVkaW9iNjQ="},
    }


def test_build_messages_with_crops():
    p = OpenAICompatibleProvider()
    messages = _build_messages(
        {
            "system_prompt": "S",
            "user_content": "U",
            "video_base64": "dmlkZW8=",
            "crops": [
                {"media_type": "image/png", "data": "Y3JvcDE="},
                {"media_type": "image/jpeg", "data": "Y3JvcDI="},
            ],
        },
        p,
    )
    user_content = messages[1]["content"]
    # text + video + crop1 + crop2
    assert len(user_content) == 4
    assert user_content[2] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,Y3JvcDE="},
    }
    assert user_content[3] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,Y3JvcDI="},
    }


def test_build_messages_no_video_no_audio_just_text():
    """边界: 无视频无音频, 消息只含 text + crops"""
    p = OpenAICompatibleProvider()
    messages = _build_messages(
        {
            "system_prompt": "S",
            "user_content": "U",
        },
        p,
    )
    user_content = messages[1]["content"]
    # 只有 text, 没 video 没 audio
    assert user_content == [{"type": "text", "text": "U"}]


def test_build_messages_video_wins_over_audio():
    """视频和音频二选一, 视频优先 (跟原 hardcode 行为一致)"""
    p = OpenAICompatibleProvider()
    messages = _build_messages(
        {
            "system_prompt": "S",
            "user_content": "U",
            "video_base64": "dmlkZW8=",
            "audio_base64": "YXVkaW8=",  # 即使有 audio, video 优先
        },
        p,
    )
    user_content = messages[1]["content"]
    # 只有 video block, 没 audio block
    blocks = [b for b in user_content if b.get("type") in ("video_url", "input_audio")]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "video_url"
