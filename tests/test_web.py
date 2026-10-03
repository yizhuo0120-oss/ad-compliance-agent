"""Verify the Vercel entrypoint without calling paid model APIs."""
import base64
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import server
from engine.llm_client import extract_json
from engine.web_index import WebLawIndex


class FakeLLM:
    text_model = "test-text"
    vision_model = "test-vision"
    image_model = None

    def chat(self, prompt, system="", **kwargs):
        if "广告策划" in system:
            return json.dumps({"selling_points": ["便携", "易清洗"], "audience": "通勤人群", "strategy": "展示真实使用场景"})
        if "平台资深文案" in system:
            return json.dumps({"copy": "全网最低价！便携榨汁杯", "tags": ["好物分享"]})
        if "改写专家" in system:
            return json.dumps({"copy": "便携榨汁杯，限时优惠，欢迎选购", "tags": ["便携好物"]})
        if "艺术指导" in system:
            return json.dumps({"prompt": "便携榨汁杯放在明亮的厨房桌面上，商业摄影风格"})
        if "只审查海报" in system:
            return '{"findings": []}'
        if "全网最低价" in prompt.partition("给定法条")[0]:
            return json.dumps({"findings": [{"type": "极限词", "fragment": "全网最低价", "article": "广告法·第九条",
                                           "verdict": "violation", "reason": "排他性最高级评价", "suggestion": "改为限时优惠"}]})
        return '{"findings": []}'

    def vision(self, prompt, path, **kwargs):
        assert Path(path).is_file()
        self.last_image_path = Path(path)
        return json.dumps({"texts": ["全网最低价"], "visual_elements": "产品海报"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DEMO_ACCESS_TOKEN", raising=False)
    for provider in ("DEEPSEEK", "ZHIPU", "DASHSCOPE"):
        monkeypatch.delenv(f"{provider}_API_KEY", raising=False)
    return TestClient(server.app)


def test_page_and_keyword_audit_without_credentials(client):
    assert client.get("/").status_code == 200
    assert client.get("/styles.css").status_code == 200
    health = client.get("/api/health").json()
    assert health["configured"] is False
    response = client.post("/api/audit/text", json={"text": "全网最低价", "mode": "keyword"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    report = response.json()
    assert report["risk_level"] == "suspicious"
    assert any(f["law"]["quote"] for f in report["findings"])
    assert "初筛" in report["summary"]
    assert client.post("/api/audit/text", json={"text": "最低价"}).status_code == 503


def test_access_token_rejects_before_model_call(client, monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_TOKEN", "test-access-password")
    def forbidden_call():
        pytest.fail("Model should not be called before access authorization")
    monkeypatch.setattr(server, "_llm", forbidden_call)
    assert client.get("/api/health").json()["access_required"] is True
    assert client.post("/api/audit/text", json={"text": "最低价"}).status_code == 401
    assert client.post("/api/audit/text", json={"text": "最低价", "mode": "keyword"},
                       headers={"X-Demo-Token": "test-access-password"}).status_code == 200


def test_semantic_law_mapping_and_generation_rewrite(client, monkeypatch):
    monkeypatch.setattr(server, "_llm", FakeLLM)
    response = client.post("/api/audit/text", json={"text": "全网最低价"})
    report = response.json()
    assert response.status_code == 200
    assert report["risk_level"] == "violation"
    assert report["findings"][0]["law"]["article"] == "第九条"
    assert report["findings"][0]["law"]["quote"]
    product = client.post("/api/plan", json={"name": "便携榨汁杯", "info": "易清洗"}).json()
    response = client.post("/api/generate", json={"product": product, "platform": "小红书"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rounds"] == 2
    assert result["pack"]["audit"]["revisions"] == 1
    assert "最低价" not in result["pack"]["platforms"][0]["copy"]
    assert result["report"]["risk_level"] == "compliant"
    assert result["pack"]["image_path"] is None
    assert "_has_violation" not in result["report"]


def test_image_validation_and_temporary_file_cleanup(client, monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(server, "_llm", lambda: fake)
    assert client.post("/api/audit/image", json={"image": "not-base64!"}).status_code == 400
    assert client.post("/api/audit/image", json={"image": base64.b64encode(b"not an image").decode()}).status_code == 400
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    encoded = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    response = client.post("/api/audit/image", json={"image": encoded})
    assert response.status_code == 200, response.text
    assert response.json()["risk_level"] == "violation"
    assert not fake.last_image_path.exists()


def test_validation_and_bounded_payload(client):
    assert client.post("/api/audit/text", json={"text": " "}).status_code == 422
    assert client.post("/api/audit/text", json={"text": "x" * 8001}).status_code == 422
    assert client.post("/api/generate", json={"product": {"name": "杯子"}, "platform": "unknown"}).status_code == 422
    response = client.post("/api/audit/image", content=b"x" * 4_300_001,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_promo_returns_browser_image_without_persistent_disk(client, monkeypatch):
    from types import SimpleNamespace
    import engine.art_director as art
    image_bytes = io.BytesIO()
    Image.new("RGB", (640, 480), "white").save(image_bytes, format="PNG")
    image_data = image_bytes.getvalue()
    class ImageClient:
        def __init__(self):
            self._client = SimpleNamespace(with_options=lambda **options: None)
        def generate_image(self, prompt):
            return "https://image.example.test/generated.png"
    monkeypatch.setattr(server, "_llm", FakeLLM)
    monkeypatch.setattr(server, "image_client", ImageClient)
    monkeypatch.setattr(art.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(image_data))
    created_paths = []
    original_badge = art.add_ai_badge
    def remember_badge(path):
        created_paths.append(path)
        original_badge(path)
    monkeypatch.setattr(art, "add_ai_badge", remember_badge)
    response = client.post("/api/promo", json={"product": {"name": "榨汁杯"}, "copy": "便携好物，欢迎选购"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["image"].startswith("data:image/jpeg;base64,")
    assert "image_path" not in result
    assert "AI" in result["ai_disclosure"]
    assert all(not path.exists() for path in created_paths)


def test_retrieval_and_invalid_model_response():
    index = WebLawIndex()
    assert len(index.rows) == 219
    assert any(r["article"] == "第九条" and r["law"] == "广告法" for r in index.search("最高级 国家级 极限词"))
    assert extract_json('```json\n{"findings": []}\n```') == {"findings": []}
    with pytest.raises(ValueError):
        extract_json("model unavailable")


def test_malformed_model_response_is_not_reported_as_compliant(client, monkeypatch):
    class BrokenLLM(FakeLLM):
        def chat(self, *args, **kwargs):
            return '{"unexpected": "upstream-secret-message"}'
    monkeypatch.setattr(server, "_llm", BrokenLLM)
    response = client.post("/api/audit/text", json={"text": "欢迎选购"})
    assert response.status_code == 502
    assert "upstream-secret-message" not in response.text


def test_linux_image_badge_without_windows_fonts(tmp_path, monkeypatch):
    from PIL import ImageFont
    from engine.art_director import add_ai_badge
    original = ImageFont.truetype
    def no_system_fonts(font, *args, **kwargs):
        if isinstance(font, str):
            raise OSError("Missing system font")
        return original(font, *args, **kwargs)
    monkeypatch.setattr(ImageFont, "truetype", no_system_fonts)
    path = tmp_path / "promo.png"
    Image.new("RGB", (640, 480), "white").save(path)
    add_ai_badge(path)
    with Image.open(path) as image:
        assert image.getpixel((600, 440)) != (255, 255, 255)
