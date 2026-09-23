"""API 后端：通过 HTTP 调用 OpenAI 兼容 chat/completions 端点的通用实现。

接入具体服务时若协议有差异，子类覆盖 _build_payload / _build_messages /
_parse_response / _image_to_data_url 钩子，并在 factory.get_model 注册 provider
分支；子类其余逻辑复用本类的通用实现。
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
from typing import Any

import numpy as np
import requests
from PIL import Image

from src.llm.base import LLMConfig, LLMError, VLMModel


class APIVLMModel(VLMModel):
    """通用 OpenAI 兼容 API 后端。"""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._api_key = self._resolve_api_key(config)
        self._validate_config(config)

    def generate(self, prompt: str, image: np.ndarray) -> str:
        self._validate_input(prompt, image)
        image_data_url = self._image_to_data_url(image)
        payload = self._build_payload(prompt, image_data_url)
        resp = self._post(payload)
        return self._parse_response(resp)

    # —— 配置校验与鉴权（§6.4 / §5.2） ——

    def _resolve_api_key(self, config: LLMConfig) -> str | None:
        if not isinstance(config.api_key_env, str) or config.api_key_env == "":
            raise ValueError(
                f"api_key_env 必须是非空 str，收到 {config.api_key_env!r}"
            )
        if config.api_key is not None and not isinstance(config.api_key, str):
            raise ValueError(
                f"api_key 必须是 str 或 None，收到 {type(config.api_key).__name__}"
            )
        if config.api_key:  # 显式非空 → 优先，不读环境变量
            return config.api_key
        env = os.environ.get(config.api_key_env)  # None 或空串回退环境变量
        return env if env else None

    def _validate_config(self, config: LLMConfig) -> None:
        if not isinstance(config.model, str) or config.model == "":
            raise ValueError(f"model 必须是非空 str，收到 {config.model!r}")
        if not isinstance(config.base_url, str) or config.base_url == "":
            raise ValueError(f"base_url 必须是非空 str，收到 {config.base_url!r}")
        if (
            isinstance(config.timeout, bool)
            or not isinstance(config.timeout, (int, float))
            or not math.isfinite(config.timeout)
            or config.timeout <= 0
        ):
            raise ValueError(f"timeout 必须是有限正数，收到 {config.timeout!r}")
        if (
            isinstance(config.max_tokens, bool)
            or not isinstance(config.max_tokens, int)
            or config.max_tokens <= 0
        ):
            raise ValueError(f"max_tokens 必须是正整数，收到 {config.max_tokens!r}")
        if (
            isinstance(config.temperature, bool)
            or not isinstance(config.temperature, (int, float))
            or not math.isfinite(config.temperature)
        ):
            raise ValueError(
                f"temperature 必须是有限数值，收到 {config.temperature!r}"
            )

    # —— 可覆盖钩子：请求构造（§6.1 / §6.2） ——

    def _build_payload(self, prompt: str, image_data_url: str) -> dict:
        return {
            "model": self._config.model,
            "messages": self._build_messages(prompt, image_data_url),
            "max_tokens": self._config.max_tokens,
            "temperature": float(self._config.temperature),
        }

    def _build_messages(self, prompt: str, image_data_url: str) -> list[dict]:
        return [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

    def _image_to_data_url(self, image: np.ndarray) -> str:
        img = Image.fromarray(image, mode="RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    # —— HTTP 请求（§6.5：只包装已知网络 / 响应协议错误） ——

    def _post(self, payload: dict) -> Any:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self._config.timeout
            )
        except requests.exceptions.Timeout as exc:
            raise LLMError(f"请求超时（>{self._config.timeout}s）") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMError(f"网络连接失败: {exc}") from exc
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise LLMError(f"HTTP {response.status_code}: {exc}") from exc
        try:
            return response.json()
        except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as exc:
            raise LLMError("响应体不是合法 JSON") from exc

    # —— 响应解析（§6.3 / §6.5） ——

    def _parse_response(self, resp: Any) -> str:
        if not isinstance(resp, dict):
            raise LLMError(f"响应 JSON 根必须是对象，收到 {type(resp).__name__}")
        choices = resp.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMError("响应缺少非空 choices 列表")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMError("choices[0] 必须是对象")
        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMError("choices[0] 缺少 message 对象")
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMError(f"message.content 必须是 str，收到 {type(content).__name__}")
        return content
