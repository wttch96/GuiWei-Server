"""AI 提示词读取、保存与恢复默认。

数据库中的覆盖值优先；没有保存过时回退到 prompt_defaults 里的内置提示词。
"""
from app.extensions import db
from app.models import AiPrompt
from app.services.prompt_defaults import CHAT_SYSTEM_PROMPT, VISION_PROMPT
from app.utils.errors import ApiError
from app.utils.serialize import iso

PROMPT_DEFINITIONS = {
    "chat": {
        "title": "AI 对话系统提示词",
        "description": "控制收纳助手如何理解需求、调用工具和回复。",
        "default": CHAT_SYSTEM_PROMPT,
        "hint": "支持占位符 {today}（今天日期）与 {weather}（系统每小时更新的天津天气）。保存后对新的对话立即生效。",
        "max_length": 20000,
    },
    "vision": {
        "title": "拍照识图提示词",
        "description": "控制视觉模型从照片中提取的字段，以及分类、标签和色系的判断方式。",
        "default": VISION_PROMPT,
        "hint": "识图要求模型只输出 JSON；请保留 color_family 字段，否则无法自动填充色系。",
        "max_length": 20000,
    },
}


def _definition(key: str) -> dict:
    definition = PROMPT_DEFINITIONS.get(key)
    if not definition:
        raise ApiError("提示词不存在", 404)
    return definition


def get_prompt(key: str) -> str:
    definition = _definition(key)
    row = db.session.get(AiPrompt, key)
    content = (row.content or "").strip() if row else ""
    return content or definition["default"]


def get_chat_prompt() -> str:
    return get_prompt("chat")


def get_vision_prompt() -> str:
    return get_prompt("vision")


def _serialize(key: str) -> dict:
    definition = _definition(key)
    row = db.session.get(AiPrompt, key)
    content = (row.content or "").strip() if row else ""
    return {
        "key": key,
        "title": definition["title"],
        "description": definition["description"],
        "hint": definition["hint"],
        "content": content or definition["default"],
        "default_content": definition["default"],
        "is_custom": bool(content),
        "max_length": definition["max_length"],
        "updated_at": iso(row.updated_at) if row else None,
    }


def list_prompts() -> list[dict]:
    return [_serialize(key) for key in PROMPT_DEFINITIONS]


def update_prompt(key: str, content: str) -> dict:
    definition = _definition(key)
    content = (content or "").strip()
    if len(content) < 20:
        raise ApiError("提示词太短，至少需要 20 个字符", 422)
    if len(content) > definition["max_length"]:
        raise ApiError(f"提示词不能超过 {definition['max_length']} 个字符", 422)

    row = db.session.get(AiPrompt, key)
    if row:
        row.content = content
    else:
        db.session.add(AiPrompt(key=key, content=content))
    db.session.commit()
    return _serialize(key)


def reset_prompt(key: str) -> dict:
    _definition(key)
    row = db.session.get(AiPrompt, key)
    if row:
        db.session.delete(row)
        db.session.commit()
    return _serialize(key)
