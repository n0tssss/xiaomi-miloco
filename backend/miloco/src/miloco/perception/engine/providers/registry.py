"""Provider registry — 3 层检测机制的工厂。

Layer 1 (config 优先): 用户在 config.yaml 里显式写 ``provider: minimax``
                     → 直接用,不走任何 URL 检测
Layer 2 (registry 遍历): 每个 provider 自己声明认什么 base_url
                          (matches_url 返回 True 的第一个胜出)
Layer 3 (兜底默认): OpenAICompatibleProvider(任何 URL 都接受)

设计要点:
- 不写正则,纯字符串匹配(避免 false positive)
- ``_PROVIDERS`` 字典声明顺序 = registry 遍历优先级
  (新 provider 加在前面会被优先匹配,这是想要的:越专用的 provider 越早匹配)
- ``get_provider`` 加 LRU cache,启动时算一次,配置变了 ``clear_cache()``
- 每加一个新 provider 只需要:
    1. 在 providers/ 下加个文件,定义 Provider 类
    2. 在 registry.py 末尾加一行 ``register_provider("myprovider", MyProviderClass)``
  核心代码 0 改动。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Type

from miloco.perception.engine.providers.base import OmniProvider
from miloco.perception.engine.providers.openai_compatible import (
    OpenAICompatibleProvider,
)


# 已注册的 provider 类表(name -> class)
# 顺序敏感:OpenAICompatibleProvider 放最后,作为兜底
# 加新 provider 时插在它前面。
_PROVIDERS: dict[str, Type[OmniProvider]] = {}


def register_provider(name: str, cls: Type[OmniProvider]) -> None:
    """注册一个 provider 类到 registry。

    一般在 provider 文件末尾调用,例如::

        # providers/minimax.py
        from miloco.perception.engine.providers.registry import register_provider

        class MiniMaxProvider:
            name = "minimax"
            ...

        register_provider("minimax", MiniMaxProvider)
    """
    if not issubclass(cls, OmniProvider) and not hasattr(cls, "video_block"):
        raise TypeError(
            f"{cls.__name__} must implement OmniProvider Protocol "
            f"(video_block/audio_block/etc.)"
        )
    # 如果 name 已注册,后注册的覆盖前面的(允许 monkey-patch 测试)
    _PROVIDERS[name] = cls


def get_provider_class(name: str) -> Type[OmniProvider] | None:
    """按名字查 provider 类,无则 None(给调用方处理 fallback)。"""
    return _PROVIDERS.get(name)


def list_provider_names() -> list[str]:
    """返回所有已注册 provider 名字,用于 admin UI / config 校验。"""
    return list(_PROVIDERS.keys())


def clear_cache() -> None:
    """清掉 get_provider() 的 LRU cache(配置改了之后调用)。"""
    get_provider.cache_clear()


@lru_cache(maxsize=1)
def get_provider(
    base_url: str,
    declared: str | None = None,
) -> OmniProvider:
    """3 层检测机制的工厂入口。

    Args:
        base_url:  配置的 model.omni.base_url
        declared:  配置的 model.omni.provider (用户显式声明,优先)

    Returns:
        一个 OmniProvider 实例(永远不返回 None,总有兜底)

    Examples::

        provider = get_provider(
            base_url=settings.model.omni.base_url,
            declared=settings.model.omni.provider,
        )
        video_block = provider.video_block(video_b64, fps=3, audio_b64=pcm)
        audio_block = provider.audio_block(audio_b64, sample_rate=16000)
    """
    # Layer 1: 配置层(用户显式声明,最优先)
    if declared:
        cls = _PROVIDERS.get(declared)
        if cls is not None:
            return cls()
        # 配置了不存在的名字 → 记日志,继续走 Layer 2/3 兜底
        import logging
        logging.getLogger(__name__).warning(
            "provider=%r configured but not registered (known=%s), "
            "falling back to URL match",
            declared, list(_PROVIDERS.keys()),
        )

    # Layer 2: provider 自己声明的 URL 字符串匹配(不是正则)
    # 顺序遍历,第一个 matches_url() 为 True 的胜出
    for cls in _PROVIDERS.values():
        try:
            if cls().matches_url(base_url):
                return cls()
        except Exception:  # noqa: BLE001
            # provider 的 matches_url 不能抛(让它失败不影响其他 provider)
            continue

    # Layer 3: 兜底默认(OpenAI 兼容)
    # _PROVIDERS 字典的最后一项就是 OpenAICompatibleProvider(默认注册时插入)
    # 直接拿最后一项
    fallback_cls = next(reversed(list(_PROVIDERS.values())))
    return fallback_cls()


# === 默认注册 ===
# 注意顺序: 越专用的 provider 越靠前(优先匹配),OpenAI 兼容放最后(兜底)
# 当前只有 OpenAI 兼容;PR2 会加 MiniMax,放在 OpenAI 前面。
register_provider("openai", OpenAICompatibleProvider)
# PR2 加这里:
# register_provider("minimax", MiniMaxProvider)
# PR4 加:
# register_provider("qwen_vl", QwenVLProvider)
# register_provider("gemini", GeminiProvider)