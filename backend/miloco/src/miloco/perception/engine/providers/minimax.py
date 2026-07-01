"""MiniMax provider — MiniMax-M3 适配层。

唯一跟 OpenAICompatible 的差异: MiniMax **不支持 audio 通道** —— 没有
``input_audio`` 块,音频必须 mux 进 mp4 视频流一起发。其他 wire format
(``{type: video_url, video_url: {url, fps}, media_resolution: "max"}``)、
thinking(默认开、嵌 content)、request_kwargs(无 extras)完全跟 OpenAI 一样。

所以本 provider 只 override 4 个 method:
- ``video_block`` 加 ffmpeg mux 行为(audio_b64 非空时把 PCM 塞进 mp4)
- ``audio_block`` 返 None(没 audio 通道)
- ``supports_audio_only`` 返 False(必须发视频)
- ``merge_audio_into_video`` 返 True(描述能力)
- ``request_kwargs`` 返 ``{}``(沿用 caller 标准 envelope,不替 user 画 cap)
- ``matches_url`` 返 ``"minimaxi" in base_url.lower()``(URL 字符串匹配,不开正则)

加新 provider 走 registry.register_provider("minimax", MiniMaxProvider) 一行,核心
代码 0 改动 —— 这就是 PR3 设计目标的兑现。
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from typing import Any

from miloco.perception.engine.providers.openai_compatible import (
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)


# ffmpeg mux 输出临时文件后缀(扩展名决定容器 sniff 路径,固定 .mp4)
_MUX_OUT_SUFFIX = ".mp4"


def _mux_pcm_into_mp4(
    video_b64: str,
    audio_b64: str,
    audio_sample_rate: int,
) -> str:
    """把 audio_b64(原始 PCM/wav/m4a bytes)塞进 video_b64(mp4)视频流。

    返回新的 mp4 base64(无 audio block,音频已 mux 进视频轨道)。
    失败返 None —— caller fallback 到无 audio 的 video block。

    关键技术:
    - ffmpeg 临时文件读写,失败时清理(避免 /tmp 残留)
    - ``-c:v copy`` 不重编视频,只加音轨,保持原视频质量
    - ``-c:a aac`` 把任意 PCM 源编成 AAC(MiniMax 接受的)
    - ``-map 0:v -map 1:a`` 显式指定流映射(避免 ffmpeg 自动选错流)
    """
    try:
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as v_in,
            tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as a_in,
            tempfile.NamedTemporaryFile(suffix=_MUX_OUT_SUFFIX, delete=False) as v_out,
        ):
            v_in_path, a_in_path, v_out_path = v_in.name, a_in.name, v_out.name
            v_in.write(base64.b64decode(video_b64))
            a_in.write(base64.b64decode(audio_b64))
    except Exception as exc:
        logger.warning("MiniMax mux: temp file create failed: %s", exc)
        return None

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", v_in_path,
                "-i", a_in_path,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "64k",
                "-ar", str(audio_sample_rate),
                "-ac", "1",
                v_out_path,
            ],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning(
                "MiniMax mux: ffmpeg failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="ignore")[-300:],
            )
            return None
        with open(v_out_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("MiniMax mux: ffmpeg exec failed: %s", exc)
        return None
    finally:
        for p in (v_in_path, a_in_path, v_out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


class MiniMaxProvider(OpenAICompatibleProvider):
    """MiniMax-M3 provider。

    继承 OpenAICompatibleProvider,只 override 音频处理相关的 4 个 method:
    audio_block 返 None、supports_audio_only 返 False、merge_audio_into_video
    返 True、video_block 在 audio_b64 非空时调 ffmpeg mux。其他 wire format
    (request_kwargs / matches_url / video_block 无 audio 时)完全用父类。
    """

    name = "minimax"

    def video_block(
        self,
        video_b64: str | None,
        fps: int,
        audio_b64: str | None = None,
        audio_sample_rate: int = 16000,
    ) -> dict | None:
        """OpenAI 兼容: 标准 video_url 块。

        - 无 audio: 跟 OpenAI 一致({type:video_url, video_url:{url, fps}, media_resolution})
        - 有 audio: 先用 ffmpeg mux 进 mp4,再返新 mp4 的 video_url 块
          (audio 不另发,MiniMax 没 input_audio 通道)
        - mux 失败: 返 video-only 块(降级,audio 丢 —— 失败概率低)
        """
        if not video_b64:
            return None
        if audio_b64:
            muxed_b64 = _mux_pcm_into_mp4(video_b64, audio_b64, audio_sample_rate)
            if muxed_b64:
                return {
                    "type": "video_url",
                    "video_url": {"url": f"data:video/mp4;base64,{muxed_b64}"},
                    "fps": fps,
                    "media_resolution": "max",
                }
            logger.warning(
                "MiniMax mux 失败,fallback 到 video-only block(audio 丢)"
            )
        return {
            "type": "video_url",
            "video_url": {"url": f"data:video/mp4;base64,{video_b64}"},
            "fps": fps,
            "media_resolution": "max",
        }

    def audio_block(self, audio_b64: str, sample_rate: int) -> dict | None:
        """MiniMax 没独立 audio 通道 —— audio 已在 video_block 里 mux 完。

        返 None 不等于丢音频(这是 PR3 design 重要约定),是"已经 mux 进 video,
        不要独立再发"。具体走 video_block 的 audio_b64 路径。
        """
        return None

    def supports_audio_only(self) -> bool:
        """MiniMax 必须发视频(没 audio-only 通道)。"""
        return False

    def merge_audio_into_video(self) -> bool:
        """MiniMax 的 audio 走 video mux 路径(描述能力,caller 不会调,但保留供 tracing)。"""
        return True

    def request_kwargs(
        self, payload: dict, fps: int, **kwargs: Any
    ) -> dict[str, Any]:
        """MiniMax thinking 默认开、不需要 envelope extras,跟 OpenAI 一样返 {}。

        实测 (curl 测试 #1-#6): MiniMax-M3 接受 OpenAI 兼容 chat completion
        格式,``<think>`` 默认嵌 content,无独立 reasoning_content 字段,也不需要
        显式 thinking.budget_tokens 之类的 envelope。request_kwargs 走 OpenAI 父类
        返 {} 即可。
        """
        return {}

    def matches_url(self, base_url: str) -> bool:
        """URL 字符串匹配,不用正则(避免 false positive)。

        MiniMax 官方 base_url 形如 https://api.minimaxi.com/v1,子串 "minimaxi" 即可覆盖。
        registry 按 _PROVIDERS 字典顺序遍历,这个 provider 注册在 OpenAI 之前
        (所以优先 match),兜底是 OpenAICompatibleProvider(任何 URL 都接受)。
        """
        return "minimaxi" in base_url.lower()


# === 默认注册 ===
# 在 registry 末尾 ``register_provider("minimax", MiniMaxProvider)`` 一行,
# _PROVIDERS 字典顺序敏感(声明顺序 = Layer 2 遍历优先级):
#   registry 必须把 "minimax" 注册在 "openai" 之前 —— 否则 Layer 2 顺序
#   遍历到 minimax 之前已经 match 到了 OpenAICompatibleProvider(也返 True),
#   minimax 永远轮不到。
