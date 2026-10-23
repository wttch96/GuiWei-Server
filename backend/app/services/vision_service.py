"""视觉识图服务。

通过 DeepSeek 的 OpenAI 兼容 /chat/completions 接口调用多模态模型。
deepseek-flash 支持图片输入（image_url + base64 data URL），默认复用
DEEPSEEK_API_BASE / DEEPSEEK_API_KEY；也可用 VISION_* 指向其它兼容网关。
未配置密钥时接口明确返回 503。
"""
import base64
import json
from pathlib import Path

import requests
from flask import current_app

from app.models import COLOR_FAMILIES, Photo
from app.services import photo_service, prompt_service
from app.utils.errors import ApiError
from app.utils.serialize import dumps

# 识别结果里常见的颜色词 → 固定色系。顺序很重要（先白后米、先灰后银等）。
_COLOR_HINTS = (
    ("黑", "黑色"),
    ("白", "白色"),
    ("灰", "灰色"),
    ("银", "灰色"),
    ("米", "米色"),
    ("卡其", "米色"),
    ("驼", "米色"),
    ("棕", "棕色"),
    ("咖", "棕色"),
    ("褐", "棕色"),
    ("红", "红色"),
    ("橙", "橙色"),
    ("黄", "黄色"),
    ("金", "黄色"),
    ("绿", "绿色"),
    ("青", "青色"),
    ("蓝", "蓝色"),
    ("紫", "紫色"),
    ("粉", "粉色"),
    ("彩", "彩色"),
    ("花", "彩色"),
    ("多色", "彩色"),
)


def normalize_color_family(value) -> str:
    """把模型返回的颜色描述收敛到固定色系，无法判断时返回空字符串。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if text in COLOR_FAMILIES:
        return text
    for hint, family in _COLOR_HINTS:
        if hint in text:
            return family
    return "其他"


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
        "color_family": normalize_color_family(result.get("color_family")),
        "location_hint": str(result.get("location_hint") or "").strip(),
        "confidence": max(0.0, min(1.0, confidence)),
        "raw_text": str(result.get("raw_text") or "").strip(),
        "raw_content": raw_content,
    }


def analyze_photo(photo: Photo) -> dict:
    if not is_configured():
        raise ApiError(
            "未配置视觉模型。请设置 DEEPSEEK_API_KEY，或在 .env 中配置 VISION_API_BASE / VISION_API_KEY / VISION_MODEL（需为 OpenAI 兼容的多模态接口）",
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
                    {"type": "text", "text": prompt_service.get_vision_prompt()},
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
            "color_family": "",
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
