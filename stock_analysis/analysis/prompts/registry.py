"""
Prompt 版本注册表。

切换版本：修改 CURRENT_VERSION 即可。
新增版本：在本目录新建 v2.py 并在 _VERSION_MAP 中注册。
"""
from __future__ import annotations
import importlib
from typing import Any

CURRENT_VERSION = "v2"

_VERSION_MAP = {
    "v1": "stock_analysis.analysis.prompts.v1",
    "v2": "stock_analysis.analysis.prompts.v2",
}


def get_current_version() -> str:
    return CURRENT_VERSION


def load_prompt_config(version: str | None = None) -> Any:
    """加载指定版本（默认当前版本）的 prompt 配置模块。"""
    v = version or CURRENT_VERSION
    module_path = _VERSION_MAP.get(v)
    if not module_path:
        raise ValueError(f"未知 prompt 版本: {v}，可用版本: {list(_VERSION_MAP)}")
    return importlib.import_module(module_path)
