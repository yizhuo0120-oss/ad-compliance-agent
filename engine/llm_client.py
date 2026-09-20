"""统一 LLM 客户端 —— 供应商/模型切换只改 .env，代码零改动。

用法：
    from engine.llm_client import LLMClient
    llm = LLMClient()                      # 用 .env 里 LLM_PROVIDER 指定的供应商
    llm = LLMClient(provider="zhipu")      # 临时切到智谱
    text = llm.chat("把这句话改写为合规文案：全网最低价")
    out  = llm.chat(prompt, json_mode=True)          # 强制 JSON 输出（D6 判断用）
    desc = llm.vision("逐字转写图中文字", poster.png)  # 图像输入（D7 用）

.env 可配置项（见 .env.example）：
    LLM_PROVIDER=deepseek | zhipu | dashscope
    <PROVIDER>_API_KEY / _BASE_URL / _TEXT_MODEL / _VISION_MODEL
"""
from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KNOWN_PROVIDERS = ("deepseek", "zhipu", "dashscope")

# 三家均为 OpenAI 兼容接口；base_url 与模型名可被 .env 同名变量覆盖
# image 模型：None = 该供应商无生图能力（deepseek-flash 只能看图不能生图）
_DEFAULTS = {
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-flash", "deepseek-flash", None),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-5.3", "glm-4v-flash", "cogview-3-flash"),
    "dashscope": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", "qwen-vl-max", "wanx2.1-t2i-turbo"),
}


class LLMClient:
    """OpenAI 兼容接口的统一客户端。"""

    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "deepseek")).strip().lower()
        cfg = self._load_cfg(self.provider)
        self.text_model = cfg["text_model"]
        self.vision_model = cfg["vision_model"]
        self.image_model = cfg["image_model"]
        self._client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])

    @staticmethod
    def _load_cfg(provider: str) -> dict:
        prefix = provider.upper()
        api_key = os.getenv(f"{prefix}_API_KEY", "")
        if provider not in _DEFAULTS or not api_key:
            raise ValueError(
                f"供应商 {provider!r} 未配置：请检查 .env 的 LLM_PROVIDER 与 {prefix}_API_KEY"
            )
        dft_base, dft_text, dft_vision, dft_image = _DEFAULTS[provider]
        return {
            "api_key": api_key,
            "base_url": os.getenv(f"{prefix}_BASE_URL", dft_base),
            "text_model": os.getenv(f"{prefix}_TEXT_MODEL", dft_text),
            "vision_model": os.getenv(f"{prefix}_VISION_MODEL", dft_vision),
            "image_model": os.getenv(f"{prefix}_IMAGE_MODEL", dft_image),
        }

    def chat(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """文本调用。json_mode=True 时强制 JSON 输出（D6 逐条判断用）。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict = {"model": model or self.text_model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    def vision(self, prompt: str, image_path: str | Path, model: str | None = None) -> str:
        """图像调用：本地图片转 base64 data URL（D7 海报转写/视觉判定用）。"""
        image_path = Path(image_path)
        mime = mimetypes.guess_type(image_path)[0] or "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }]
        resp = self._client.chat.completions.create(model=model or self.vision_model, messages=messages)
        return (resp.choices[0].message.content or "").strip()

    def generate_image(self, prompt: str, size: str = "1024x1024",
                       model: str | None = None) -> str:
        """生图：返回图片 URL（卡8 宣传图用）。供应商无生图能力时抛错。"""
        if not self.image_model:
            raise ValueError(f"供应商 {self.provider!r} 未配置生图模型（{self.provider.upper()}_IMAGE_MODEL）")
        resp = self._client.images.generate(model=model or self.image_model, prompt=prompt, size=size)
        return resp.data[0].url


if __name__ == "__main__":
    c = LLMClient()
    print(f"provider={c.provider}  text_model={c.text_model}  vision_model={c.vision_model}")
