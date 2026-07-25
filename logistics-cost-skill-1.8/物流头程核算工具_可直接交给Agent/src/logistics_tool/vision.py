from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .utils import load_dotenv


class AgentRequiredError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 120) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"视觉接口返回 HTTP {exc.code}: {body[:800]}") from exc


class VisionAnalyzer:
    def __init__(self, root: Path):
        self.root = root
        load_dotenv(root / ".env")
        self.prompt = (root / "config" / "vision_prompt.txt").read_text(encoding="utf-8")

    def detect_provider(self, requested: str = "auto") -> str:
        if requested not in {"", "auto", None}:
            return requested
        configured = os.getenv("VISION_PROVIDER", "agent").strip().lower()
        if configured != "agent":
            return configured
        if os.getenv("OPENAI_COMPATIBLE_API_KEY") and os.getenv("OPENAI_COMPATIBLE_MODEL"):
            return "openai_compatible"
        if os.getenv("OLLAMA_MODEL"):
            return "ollama"
        return "agent"

    def analyze(self, image_path: Path, provider: str = "auto") -> dict[str, Any]:
        provider = self.detect_provider(provider)
        if provider == "agent":
            raise AgentRequiredError("未配置视觉 API。本项目已生成 Agent 分析模板，请让 Agent 按 AGENTS.md 看图并填写。")
        if provider == "openai_compatible":
            return self._openai_compatible(image_path)
        if provider == "ollama":
            return self._ollama(image_path)
        raise ValueError(f"不支持的视觉提供方: {provider}")

    def _openai_compatible(self, image_path: Path) -> dict[str, Any]:
        base = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
        model = os.getenv("OPENAI_COMPATIBLE_MODEL", "")
        if not key or not model:
            raise RuntimeError("缺少 OPENAI_COMPATIBLE_API_KEY 或 OPENAI_COMPATIBLE_MODEL")
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "分析这张商品图片并返回指定 JSON。"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ]},
            ],
        }
        response = _post_json(f"{base}/chat/completions", payload, {"Authorization": f"Bearer {key}"})
        content = response["choices"][0]["message"]["content"]
        return _extract_json(content)

    def _ollama(self, image_path: Path) -> dict[str, Any]:
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "")
        if not model:
            raise RuntimeError("缺少 OLLAMA_MODEL")
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": "分析这张商品图片并返回指定 JSON。", "images": [b64]},
            ],
            "options": {"temperature": 0.1},
        }
        response = _post_json(f"{base}/api/chat", payload, {})
        return _extract_json(response["message"]["content"])
