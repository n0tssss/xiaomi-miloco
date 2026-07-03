"""测试公共夹具：把 hyphen 目录 miloco-plugin/ 作为包加载进 sys.modules。

【hermes-pr.md §五 #1 完成】adapter/ 独立进程栈已删除(#1 完成),此 conftest 只
加载 miloco-plugin/。如有旧测试引用 adapter_pkg,从 sys.modules 拿(NoneType)。

miloco-plugin 目录名含连字符，不是合法 Python 包名，Hermes 走路径加载无碍，
但 pytest 直接 import 不行——这里用 importlib 以唯一别名装载，让相对导入
(``from .catalog import ...``) 能解析。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HERMES_DIR = TESTS_DIR.parent  # plugins/hermes/

_PLUGIN_DIR = HERMES_DIR / "miloco-plugin"
_HERMES_ADAPTER_DIR = HERMES_DIR / "hermes_adapter"  # #1+#4 新增的适配器子包
_ADAPTER_DIR_LEGACY = HERMES_DIR / "adapter"  # #1 完成 已删,保留空目录兼容


def _load_pkg(alias: str, pkg_dir: Path) -> None:
    if not pkg_dir.is_dir():
        # 子目录缺失时静默跳过(避免 #1 完成后测试加载失败)
        sys.modules[alias] = None  # type: ignore[assignment]
        return
    if alias in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        alias,
        pkg_dir / "__init__.py",
        submodule_search_locations=[str(pkg_dir)],
    )
    if spec is None or spec.loader is None:
        sys.modules[alias] = None  # type: ignore[assignment]
        return
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)


def _load_single(alias: str, file: Path) -> None:
    """加载无相对导入的独立模块（如 session_map.py）。"""
    if alias in sys.modules:
        return
    if not file.is_file():
        sys.modules[alias] = None  # type: ignore[assignment]
        return
    spec = importlib.util.spec_from_file_location(alias, file)
    if spec is None or spec.loader is None:
        sys.modules[alias] = None  # type: ignore[assignment]
        return
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)


# 适配进程：作为包 adapter_pkg 装载(#1 完成 — 已删,这里 stub 给旧测试用)
_load_pkg("adapter_pkg", _ADAPTER_DIR_LEGACY)

# 适配器子包: hermes_adapter(主线 #1 新增)— 装载供 test_hermes_adapter.py 用
sys.path.insert(0, str(HERMES_DIR))

# 插件：作为包 miloco_plugin_pkg 装载（context_injection/tools_* 间有相对导入）
_load_pkg("miloco_plugin_pkg", _PLUGIN_DIR)

# ---------------------------------------------------------------------------
# Hermes API 契约测试路径：让 ``from gateway.config import Platform`` /
# ``from gateway.delivery import DeliveryTarget`` 在 plugins/hermes/tests/ 下可解析。
# 优先级：
#   1. ``$HERMES_AGENT_PATH`` 环境变量（CI / 显式注入）
#   2. ``<xiaomi-miloco>/../hermes-agent``（本机开发约定；sibling repo）
# 都找不到时静默跳过契约测试（不打断其他测试）。
# ---------------------------------------------------------------------------
import os as _os  # noqa: E402

_HERMES_AGENT_CANDIDATES = [
    _os.environ.get("HERMES_AGENT_PATH", "").strip() or None,
    str(HERMES_DIR.parent.parent / "hermes-agent"),
]
for _candidate in _HERMES_AGENT_CANDIDATES:
    if _candidate and Path(_candidate).is_dir() and (_candidate) not in sys.path:
        sys.path.insert(0, _candidate)
        break
