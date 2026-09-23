"""后端分发与配置加载：get_model 按 provider 返回实现，load_config 从 YAML 读配置。"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Union

import yaml

from src.llm.api import APIVLMModel
from src.llm.base import LLMConfig, VLMModel
from src.llm.local import LocalVLMModel


def get_model(config: LLMConfig) -> VLMModel:
    """按 config.provider 返回对应后端实例（唯一分发点）。

    任何新增后端（含专用适配子类）都在此注册一个 provider 分支；未知 provider
    抛 ValueError（输入契约错误，非 LLMError）。
    """
    if config.provider == "api":
        return APIVLMModel(config)
    if config.provider == "local":
        return LocalVLMModel(config)
    raise ValueError(f"未知 provider: {config.provider!r}（可选 api / local）")


def load_config(path: Union[str, Path]) -> LLMConfig:
    """从 YAML 文件加载 LLMConfig（只解析结构，不读环境变量、不做后端校验）。"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return LLMConfig()
    if not isinstance(data, dict):
        raise ValueError(f"YAML 根必须是 mapping，收到 {type(data).__name__}")
    known = {f.name for f in fields(LLMConfig)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"未知配置字段: {sorted(unknown)}")
    return LLMConfig(**data)
