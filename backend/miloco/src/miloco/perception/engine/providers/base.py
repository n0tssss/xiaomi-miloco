"""Omni provider base — 每个 Omni model 一份独立的 wire format 翻译。

背景:不同模型(MiMo / MiniMax / 未来 Gemini / Qwen-VL)对多模态 content
block 的字段位置、字段名、必填项都不同。原先硬编码在 prompt_builder +
omni_client 里,加新 provider 要改两处。把 wire format 抽到 Provider
类里,加新 provider 只加文件不动核心逻辑。

设计原则:
- Provider 是"如何把中性 payload 翻译成该模型的 wire format"
- Provider 不知道业务逻辑(路由判定、payload 装配),业务由 Builder 负责
- audio_block() 返回 None 不等于"丢音频",而是"音频已在 video 里 mux 完成"
- matches_url() 用纯字符串匹配而不是正则(避免 false positive)

实现说明: 原本用 ``@runtime_checkable Protocol``,但 Python 限制含
non-method members (如 ``name: str`` 类变量) 的 Protocol 不能做
issubclass() 检查,registry import 时直接 TypeError。改用 ABC +
abstractmethod 避免这个坑,且 issubclass() 在启动时就能 validate provider
类是否齐全。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class OmniProvider(ABC):
    """每个 Omni provider 必须继承这个 ABC 并实现 6 个方法。

    关键语义:
    - ``video_block(audio_b64=...)`` 接收 audio 参数 → MiniMax 这类没
      独立 audio 通道的 provider 可以把 PCM mux 进 mp4 音频轨。
    - ``audio_block()`` 返回 None ≠ 丢音频,而是"audio 已 mux 进 video,
      不要独立再发"。永远不要丢弃 audio 数据。
    - ``matches_url()`` 用纯字符串匹配,不用正则(避免 false positive)。
    """

    #: Provider 唯一名字,例如 "openai" / "minimax" / "qwen_vl"。
    #: 子类必须 override(类变量,不在 __init__ 里赋值,启动时直接读)。
    name: str = ""

    @abstractmethod
    def video_block(
        self,
        video_b64: str | None,
        fps: int,
        audio_b64: str | None = None,
        audio_sample_rate: int = 16000,
    ) -> dict | None:
        """返回这个 provider 的 video content block。

        关键: audio_b64/audio_sample_rate 参数是 v3 修订后新增的——
        MiniMax 这类没独立 audio 通道的 provider 需要把 PCM mux 进 mp4
        音频轨,再返回 video block。Provider 自己决定怎么 mux(ffmpeg)。

        返回 None 表示这个 provider 不需要 video 块(audio-only 场景)。
        """
        raise NotImplementedError

    @abstractmethod
    def audio_block(self, audio_b64: str, sample_rate: int) -> dict | None:
        """返回这个 provider 的 audio content block。

        返回 None 表示 **audio 已经在 video_block 里 mux 完成,不要独立再发**。
        不要用 None 表示"丢弃音频"——音频永远不应该丢。
        """
        raise NotImplementedError

    @abstractmethod
    def supports_audio_only(self) -> bool:
        """provider 是否支持"纯音频"路由(无视频)。

        OpenAI/MiMo: True(可以只发 input_audio)
        MiniMax: False(没音频通道,即使 batch 全是 audio 也必须发视频)
        """
        raise NotImplementedError

    @abstractmethod
    def merge_audio_into_video(self) -> bool:
        """provider 是否需要把 PCM mux 进 mp4 视频流。

        OpenAI/MiMo: False(有独立 input_audio 通道)
        MiniMax: True(没音频通道,必须 ffmpeg mux)
        """
        raise NotImplementedError

    @abstractmethod
    def request_kwargs(self, payload: dict, fps: int) -> dict:
        """返回 provider 在 caller 标准 envelope 之上**额外需要**的字段。

        标准 envelope (model / messages / max_tokens / temperature / top_p /
        stream) 由 caller 直接 set,user config 决定。Provider **不**替 user
        画 cap,只在该 provider 真正需要的 model-specific 字段上返 dict。

        典型用法:
        - OpenAI/MiMo: 返 {} (无额外字段,标准 envelope 够用)
        - MiniMax-M3 (thinking-on): 返 ``{"thinking": {"type": "enabled",
          "budget_tokens": 1024}}`` 之类
        - 一些 provider 返 ``{"stream_options": {...}}`` 之类微调

        audio/video mux 等 wire-format 行为由 ``video_block()`` /
        ``audio_block()`` / ``merge_audio_into_video()`` 各自定义 ——
        request_kwargs 跟 wire format 无关,只管 envelope-level extras。

        返回 {} 表示无额外字段,caller 的 body 不动。
        """
        raise NotImplementedError

    @abstractmethod
    def matches_url(self, base_url: str) -> bool:
        """这个 provider 认什么 base_url pattern。

        用纯字符串匹配 (``"minimaxi" in base_url.lower()``),不用正则:
        - 加新 provider 时开发者知道 URL 长什么样
        - 子串匹配稳定(各种子域名都覆盖)
        - registry 顺序决定优先级(谁先注册谁先匹配)
        """
        raise NotImplementedError