"""视觉识图服务。

通过 OpenAI 兼容的 /chat/completions 接口调用视觉模型（如 DeepSeek-VL2）。
DeepSeek 官方文本 chat 接口不支持图片，须在 .env 中配置 VISION_* 指向可用的
OpenAI 兼容视觉网关；未配置时接口明确返回 503。
"""
import base64
import json
from pathlib import Path

import requests
from flask import current_app

from app.models import Photo
from app.services import photo_service
from app.utils.errors import ApiError
from app.utils.serialize import dumps

VISION_PROMPT = """你是专业的家庭收纳整理助手。请识别照片中的主要物品，判断它是什么、数量，并给出适合的中文大类、标签和收纳位置建议。

只输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释。字段如下：
{
  "name": "物品名称，简短准确",
  "description": "外观、材质、用途的简要描述",
  "category": "物品大类，例如 电子产品/日用品/衣物/证件/药品/工具/食品",
  "tags": ["3-8 个中文标签"],
  "quantity": 1,
  "location_hint": "建议收纳位置，例如 书房/抽屉",
  "confidence": 0.0,
  "raw_text": "照片中清晰可见的文字；没有则为空字符串"
}

要求：quantity 必须是整数；confidence 为 0-1 的小数；不确定时给最可能的判断，不要编造看不清的文字。"""


def is_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("VISION_API_BASE") and cfg.get("VISION_API_KEY") and cfg.get("VISION_MODEL"))


def status() -> dict:
    cfg = current_app.config
    return {
        "configured": is_configured(),
        "api_base": cfg.get("VISION_API_BASE") if is_configured() else None,
        "model": cfg.get("VISION_MODEL") or None,
    }


def _endpoint() -> str:
    base = (current_app.config.get("VISION_API_BASE") or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:])
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize(result: dict, raw_content: str) -> dict:
    tags = result.get("tags") or []
    if isinstance(tags, str):
        tags = [item for item in tags.replace("，", ",").split(",")]
    tags = [str(item).strip() for item in tags if str(item).strip()][:8]

    try:
        quantity = int(result.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 0:
        quantity = 0

    try:
        confidence = float(result.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "name": str(result.get("name") or "").strip()[:200],
        "description": str(result.get("description") or "").strip(),
        "category": str(result.get("category") or "").strip(),
        "tags": tags,
        "quantity": quantity,
        "location_hint": str(result.get("location_hint") or "").strip(),
        "confidence": max(0.0, min(1.0, confidence)),
        "raw_text": str(result.get("raw_text") or "").strip(),
        "raw_content": raw_content,
    }


def analyze_photo(photo: Photo) -> dict:
    if not is_configured():
        raise ApiError(
            "未配置视觉模型。请在 .env 中设置 VISION_API_BASE / VISION_API_KEY / VISION_MODEL（需为 OpenAI 兼容的多模态接口）",
            503,
        )
    cfg = current_app.config
    path = photo_service.photo_abs_path(photo)
    if not path.is_file():
        raise ApiError("照片文件不存在", 404)
    raw = path.read_bytes()
    data_url = f"data:{photo.mime_type};base64,{base64.b64encode(raw).decode('ascii')}"

    payload = {
        "model": cfg["VISION_MODEL"],
        "temperature": 0,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg['VISION_API_KEY']}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            _endpoint(),
            headers=headers,
            json=payload,
            timeout=int(cfg.get("VISION_TIMEOUT") or 120),
        )
    except requests.RequestException as exc:
        raise ApiError(f"连接视觉模型失败: {exc}", 502) from exc

    if response.status_code >= 400:
        raise ApiError(
            f"视觉模型调用失败（HTTP {response.status_code}）: {response.text[:300]}", 502
        )
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ApiError("视觉模型返回格式异常", 502) from exc
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )

    parsed = _extract_json(content)
    if parsed is None:
        normalized = {
            "name": "",
            "description": content.strip()[:1000],
            "category": "",
            "tags": [],
            "quantity": 1,
            "location_hint": "",
            "confidence": 0.0,
            "raw_text": content.strip(),
            "raw_content": content,
            "parse_error": True,
        }
    else:
        normalized = _normalize(parsed, content)

    photo.ai_text = content
    photo.ai_result = dumps(normalized)
    return normalized
