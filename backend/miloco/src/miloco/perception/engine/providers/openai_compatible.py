"""OpenAI 兼容 provider — 默认 provider,行为与原 miloco 一致。

对应模型: MiMo / OpenAI / 任何 OpenAI-compatible chat completion API
接受 type=video_url + video_url={url,fps} + media_resolution + input_audio 形态。

This is the "no behavior change" baseline that PR1 needs to preserve.
All 66 existing tests must still pass after the refactor.
"""

from __future__ import annotations

import logging
from typing import Any

from miloco.perception.engine.providers.base import OmniProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(OmniProvider):
    """Default provider, preserves pre-v3 behavior exactly.

    Wire format:
        video:  {"type": "video_url", "video_url": {"url": data:video/mp4;base64,...},
                 "fps": int, "media_resolution": "max"}
        audio:  {"type": "input_audio", "input_audio": {"data": data:audio/m4a;base64,...}}

    Audio handling:
        - supports_audio_only() = True (audio route available)
        - merge_audio_into_video() = False (independent audio channel)
        - video_block ignores audio_b64 parameter (audio sent separately)
    """

    name = "openai"

    def video_block(
        self,
        video_b64: str | None,
        fps: int,
        audio_b64: str | None = None,
        audio_sample_rate: int = 16000,
    ) -> dict | None:
        """OpenAI 兼容: type=video_url + video_url={url, fps} + media_resolution。

        audio_b64 参数被忽略:OpenAI 有独立 input_audio 通道,音频不该
        mux 进 video(会双声道)。Caller 通过 audio_block() 单独发 audio。
        """
        if not video_b64:
            return None
        return {
            "type": "video_url",
            "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
            "fps": fps,
            "media_resolution": "max",
        }

    def audio_block(self, audio_b64: str, sample_rate: int) -> dict | None:
        """OpenAI 兼容: 独立 input_audio 块,data 是 m4a base64。

        注:m4a 是 _encode_batch_audio 在 caller 端做的,这里只管 wire format。
        """
        if not audio_b64:
            return None
        return {
            "type": "input_audio",
            "input_audio": {"data": f"data:audio/m4a;base64,{audio_b64}"},
        }

    def supports_audio_only(self) -> bool:
        return True

    def merge_audio_into_video(self) -> bool:
        return False

    def request_kwargs(self, payload: dict, fps: int) -> dict[str, Any]:
        """OpenAI 兼容: 标准 chat completion body,model + messages + max_tokens。

        与 provider 接口无关的 envelope(model/stream/thinking)由所有
        provider 共享实现。这里只返回 body dict,caller 负责合并其他字段。
        """
        # 注意:_build_messages 已经构造好了 messages 列表。
        # 真实使用时,caller 会把 request_kwargs() 提供的 body 字段
        # 跟 _build_messages() 输出的 messages 合并。
        # 这个方法留给 provider 扩展 envelope 字段(如 thinking / tools)。
        return {}

    def matches_url(self, base_url: str) -> bool:
        """OpenAI 兼容 provider 是默认兜底,匹配任何 URL。

        但因为 _PROVIDERS dict 中 OpenAICompatibleProvider 通常**最后**
        注册,前面的 provider 会优先 match。返回 True 是为了:
        1. 作为兜底(registry 没找到任何匹配的 provider 时返回它)
        2. 测试用(直接 instantiate OpenAICompatibleProvider)
        """
        return True