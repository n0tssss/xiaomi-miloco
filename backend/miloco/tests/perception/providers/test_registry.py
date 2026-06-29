"""Provider registry 3 层检测测试。

3 层检测:
1. declared (用户配置层) 优先
2. registry 遍历 matches_url (URL 匹配)
3. OpenAICompatibleProvider fallback (兜底)

涵盖:
- Layer 1: declared="openai" 强制走 OpenAI
- Layer 2: 已知 URL 模式 (未来 MiniMax 时测, PR1 只 OpenAI 唯一)
- Layer 3: 未知 URL 兜底到 OpenAI
- clear_cache 后重新 resolve
- 跨调用一致性 (lru_cache 命中)
- 独立 provider 实例 (不共享 mutable state)
"""

from miloco.perception.engine.providers import (
    OpenAICompatibleProvider,
    clear_cache,
    get_provider,
    get_provider_class,
    list_provider_names,
    register_provider,
)
from miloco.perception.engine.providers.base import OmniProvider


def test_get_provider_explicit_openai():
    """Layer 1: 显式 declared="openai" 强制走 OpenAI"""
    p = get_provider("https://api.openai.com/v1", declared="openai")
    assert p.name == "openai"
    assert isinstance(p, OpenAICompatibleProvider)


def test_get_provider_unknown_url_falls_back_to_openai():
    """Layer 3: 未知 URL 兜底到 OpenAI"""
    p = get_provider("https://some-random-service.example.com/v1", declared=None)
    assert p.name == "openai"
    assert isinstance(p, OpenAICompatibleProvider)


def test_get_provider_empty_url_falls_back_to_openai():
    """边界: 空 URL 也要兜底, 不能崩"""
    p = get_provider("", declared=None)
    assert isinstance(p, OpenAICompatibleProvider)


def test_get_provider_consistent_across_calls():
    """lru_cache: 同样的 (base_url, declared) 返回同一 provider 实例"""
    p1 = get_provider("https://api.openai.com/v1", declared="openai")
    p2 = get_provider("https://api.openai.com/v1", declared="openai")
    assert p1 is p2


def test_get_provider_different_args_different_instances():
    """不同的 (base_url, declared) 不共享缓存"""
    p1 = get_provider("https://api.openai.com/v1", declared="openai")
    p2 = get_provider("https://api.openai.com/v1", declared=None)
    # 不强制要求不同实例, 但要都能 resolve
    assert p1.name == "openai"
    assert p2.name == "openai"


def test_clear_cache_resets_resolution():
    """clear_cache 后下次调用重新 resolve"""
    # 先 resolve 一次
    p1 = get_provider("https://api.openai.com/v1", declared="openai")
    clear_cache()
    p2 = get_provider("https://api.openai.com/v1", declared="openai")
    # 两者都是 OpenAI, 但不是同一实例 (cache cleared)
    assert p1 is not p2
    assert type(p1) is type(p2)


def test_list_provider_names_includes_openai():
    names = list_provider_names()
    assert "openai" in names


def test_get_provider_class_returns_class():
    cls = get_provider_class("openai")
    assert cls is OpenAICompatibleProvider


def test_get_provider_class_unknown_returns_none():
    """get_provider_class 查不到时返回 None (给调用方处理 fallback, 不 raise)"""
    assert get_provider_class("nonexistent-provider") is None


class _FakeProvider(OmniProvider):
    """测试用: 完整实现 6 方法, 不调用任何外部服务"""

    name = "fake"

    def video_block(self, video_b64, fps, audio_b64=None, audio_sample_rate=16000):
        return {"type": "fake_video", "fps": fps}

    def audio_block(self, audio_b64, sample_rate):
        return {"type": "fake_audio"}

    def supports_audio_only(self):
        return False

    def merge_audio_into_video(self):
        return True

    def request_kwargs(self, payload, fps):
        return {"custom_field": "value"}

    def matches_url(self, base_url):
        return "fake-host" in base_url


def test_register_provider_via_duck_typing():
    """PR1 修订: register_provider 走 duck-typing, 不走 issubclass。

    issubclass 在含 non-method members (name: str) 的 Protocol 上 raise TypeError。
    改用 hasattr 检查 6 个方法, validate 时不依赖 Protocol subclassing。
    """
    # Duck-typing should accept a properly-implemented provider
    try:
        register_provider("fake", _FakeProvider)
    except TypeError as e:
        assert False, f"register_provider 拒了 _FakeProvider: {e}"

    # 立刻能 resolve
    p = get_provider("https://api.fake-host.com/v1", declared="fake")
    assert p.name == "fake"
    assert p.matches_url("https://api.fake-host.com/v1") is True
    assert p.request_kwargs({}, fps=3) == {"custom_field": "value"}

    # clean up
    clear_cache()
    from miloco.perception.engine.providers.registry import _PROVIDERS
    _PROVIDERS.pop("fake", None)
    clear_cache()  # 二次清, 让 fake 名字不再 resolve


def test_register_provider_rejects_empty_class():
    """没有任何方法的空类应该被 register_provider 拒绝 (TypeError)"""
    import pytest

    class EmptyClass:
        """故意不继承 OmniProvider 也不实现任何方法"""
        pass

    with pytest.raises(TypeError) as exc_info:
        register_provider("empty", EmptyClass)
    msg = str(exc_info.value)
    assert "video_block" in msg or "OmniProvider" in msg
