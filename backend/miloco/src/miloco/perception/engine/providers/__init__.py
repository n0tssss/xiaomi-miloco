"""Omni provider abstraction.

Each provider implements the ``OmniProvider`` Protocol to translate a
provider-neutral payload (video + audio base64 + fps + sample_rate)
into the wire format expected by a specific model API.

The default provider is ``OpenAICompatibleProvider`` (current miloco
behavior). New providers (e.g. MiniMax) live alongside as their own
files and self-register via ``registry.register_provider``.

Layer 2 (Builder: ``prompt_builder.py`` / ``omni_client.py``) calls
``provider.video_block(...)`` and ``provider.audio_block(...)`` to
build the OpenAI-style messages payload. The provider decides:
- type field name (video vs video_url)
- whether ``fps`` lives inside the URL object or as a sibling key
- whether ``media_resolution`` is included
- whether audio is sent as an independent block OR muxed into the video
  stream (MiniMax has no audio channel, so PCM must be muxed via ffmpeg)
- whether the model supports audio-only (no video) requests
"""

from miloco.perception.engine.providers.base import OmniProvider
from miloco.perception.engine.providers.openai_compatible import (
    OpenAICompatibleProvider,
)
from miloco.perception.engine.providers.registry import (
    clear_cache,
    get_provider,
    get_provider_class,
    list_provider_names,
    register_provider,
)

__all__ = [
    "OmniProvider",
    "OpenAICompatibleProvider",
    "clear_cache",
    "get_provider",
    "get_provider_class",
    "list_provider_names",
    "register_provider",
]