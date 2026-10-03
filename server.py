"""Vercel / ASGI 入口。运行：python -m uvicorn server:app --port 8000。"""
from __future__ import annotations

import base64
import binascii
import hmac
import io
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from openai import APIConnectionError, APIStatusError, APITimeoutError
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from engine.copywriter import plan
from engine.llm_client import LLMClient, image_client
from engine.loop import closed_loop
from engine.pipeline import audit_image, audit_text, finalize
from engine.web_index import WebLawIndex

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
MAX_IMAGE_BYTES = 3 * 1024 * 1024
app = FastAPI(title="广告合规 Agent", docs_url=None, redoc_url=None, openapi_url=None)
logger = logging.getLogger(__name__)


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TextInput(InputModel):
    text: str = Field(min_length=1, max_length=8000)
    mode: Literal["full", "keyword"] = "full"


class ImageInput(InputModel):
    image: str = Field(min_length=1, max_length=MAX_IMAGE_BYTES * 4 // 3 + 200)


class Product(InputModel):
    name: str = Field(min_length=1, max_length=100)
    info: str = Field(default="", max_length=3000)
    selling_points: list[str] = Field(default_factory=list, max_length=5)
    audience: str = Field(default="", max_length=300)
    strategy: str = Field(default="", max_length=500)


Platform = Literal["小红书", "抖音口播", "淘宝主图", "朋友圈"]


class GenerateInput(InputModel):
    product: Product
    platform: Platform


class PromoInput(InputModel):
    product: Product
    copy_text: str = Field(alias="copy", min_length=1, max_length=8000)


def require_access(x_demo_token: str = Header(default="")) -> None:
    expected = os.getenv("DEMO_ACCESS_TOKEN", "")
    if expected and not hmac.compare_digest(expected.encode(), x_demo_token.encode()):
        raise HTTPException(401, "访问口令不正确，请输入部署者提供的口令。")


@app.middleware("http")
async def api_limits(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        # Stream the body with a bound, including requests without Content-Length.
        chunks, length = [], 0
        async for chunk in request.stream():
            length += len(chunk)
            if length > 4_300_000:
                return JSONResponse({"detail": "上传内容过大，请使用小于 3 MB 的图片。"}, 413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    # Do not expose upstream messages, credentials, prompts, or temporary paths.
    logger.error("Request failed: %s", type(error).__name__)
    return JSONResponse({"detail": "处理失败，请重试或联系部署者检查运行日志。"}, 500)


def _llm() -> LLMClient:
    try:
        return LLMClient(timeout=40, max_retries=0)
    except ValueError:
        raise HTTPException(503, "尚未配置模型：请在 Vercel 环境变量中设置 LLM_PROVIDER 与对应的 API_KEY。") from None


def _invoke(operation):
    try:
        return operation()
    except HTTPException:
        raise
    except APITimeoutError:
        raise HTTPException(504, "模型响应超时，请稍后重试。") from None
    except APIStatusError as error:
        messages = {
            401: "模型服务鉴权失败，请部署者检查 API Key。",
            403: "模型服务拒绝访问，请部署者检查账号权限。",
            429: "模型服务额度不足或请求过于频繁，请稍后重试。",
        }
        raise HTTPException(502, messages.get(error.status_code, "模型调用失败，请部署者检查模型名称和服务状态。")) from None
    except APIConnectionError:
        raise HTTPException(502, "暂时无法连接模型服务，请稍后重试。") from None
    except (ValueError, TypeError, KeyError):
        raise HTTPException(502, "模型响应格式异常，请重试或检查所选模型。") from None


@lru_cache(maxsize=1)
def _index() -> WebLawIndex:
    return WebLawIndex()


@app.get("/")
def homepage():
    return FileResponse(PUBLIC / "index.html")


@app.get("/styles.css")
def stylesheet():
    return FileResponse(PUBLIC / "styles.css")


@app.get("/app.js")
def javascript():
    return FileResponse(PUBLIC / "app.js")


@app.get("/background.jpg")
def background():
    return FileResponse(PUBLIC / "background.jpg")


@app.get("/api/health")
def health():
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    configured = provider in ("deepseek", "zhipu", "dashscope") and bool(os.getenv(f"{provider.upper()}_API_KEY"))
    return {"ok": True, "configured": configured, "access_required": bool(os.getenv("DEMO_ACCESS_TOKEN")),
            "capabilities": ["text", "image", "generate"], "retrieval": "bm25"}


@app.post("/api/audit/text", dependencies=[Depends(require_access)])
def text_audit(body: TextInput):
    llm = _llm() if body.mode == "full" else type("KeywordOnly", (), {"text_model": "keyword-only"})()
    report = _invoke(lambda: audit_text(llm, body.text, _index(), use_rag="full" if body.mode == "full" else "none"))
    if body.mode == "keyword":
        report["summary"] = f"关键词初筛：命中 {len(report['findings'])} 项信号，需进一步语义审核。"
    return finalize(report)


def _decode_image(value: str) -> tuple[bytes, str]:
    if value.startswith("data:"):
        prefix, separator, value = value.partition(",")
        if not separator or prefix not in ("data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"):
            raise HTTPException(400, "仅支持 PNG、JPEG 或 WebP 图片。")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "图片编码无效，请重新选择图片。") from None
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "请选择小于 3 MB 的图片。")
    try:
        with Image.open(io.BytesIO(data)) as image:
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(image.format)
            if not suffix or image.width * image.height > 20_000_000:
                raise HTTPException(400, "图片格式不支持或尺寸超过 2000 万像素。")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "图片无法读取，请换一张图片。") from None
    return data, suffix


@app.post("/api/audit/image", dependencies=[Depends(require_access)])
def image_audit(body: ImageInput):
    data, suffix = _decode_image(body.image)
    llm = _llm()
    with tempfile.TemporaryDirectory(prefix="ad-audit-") as directory:
        path = Path(directory) / f"poster{suffix}"
        path.write_bytes(data)
        return finalize(_invoke(lambda: audit_image(llm, path, _index())))


@app.post("/api/plan", dependencies=[Depends(require_access)])
def product_plan(body: Product):
    return _invoke(lambda: plan(_llm(), body.model_dump()))


@app.post("/api/generate", dependencies=[Depends(require_access)])
def generate(body: GenerateInput):
    # Each platform is its own bounded request; image generation is a separate call.
    result = _invoke(lambda: closed_loop(_llm(), _index(), body.product.model_dump(),
                                        [body.platform], max_rounds=2, generate_image=False))
    finalize(result["report"])
    return result


@app.post("/api/promo", dependencies=[Depends(require_access)])
def promo(body: PromoInput):
    from engine.art_director import generate_promo
    try:
        image_llm = image_client()
        image_llm._client = image_llm._client.with_options(timeout=40, max_retries=0)
    except ValueError:
        raise HTTPException(503, "宣传图需要另行配置支持生图的供应商，例如 ZHIPU_API_KEY 和 ZHIPU_IMAGE_MODEL。") from None
    with tempfile.TemporaryDirectory(prefix="ad-promo-") as directory:
        result = _invoke(lambda: generate_promo(_llm(), body.product.model_dump(), body.copy_text,
                                                out_dir=Path(directory), image_llm=image_llm))
        with Image.open(result["image_path"]) as image:
            image = image.convert("RGB")
            image.thumbnail((1280, 1280))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85)
        data = buffer.getvalue()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(502, "生成图片过大，请重试。")
        return {"image": "data:image/jpeg;base64," + base64.b64encode(data).decode(),
                "image_prompt": result["image_prompt"], "ai_disclosure": result["ai_disclosure"]}
