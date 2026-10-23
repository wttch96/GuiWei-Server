"""AI 对话 / 状态 / 工具清单 / 会话历史。"""
from flask import Blueprint, g

from app.schemas.common import parse_body
from app.schemas.storage import ChatIn, PromptUpdateIn
from app.services import ai_service, prompt_service
from app.tools import get_tools
from app.utils.responses import ok

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@bp.post("/chat")
def chat():
    body = parse_body(ChatIn)
    g.source = "ai"  # 让工具产生的操作日志标记为 AI 来源
    return ok(ai_service.chat(body.message, body.session_id))


@bp.get("/status")
def status():
    return ok(ai_service.status())


@bp.get("/sessions")
def sessions():
    """会话列表：标题、消息数与累计 token。"""
    return ok(ai_service.list_sessions())


@bp.get("/sessions/<session_id>/messages")
def session_messages(session_id: str):
    return ok(ai_service.get_messages(session_id[:64]))


@bp.delete("/sessions/<session_id>")
def delete_session(session_id: str):
    return ok(ai_service.delete_session(session_id[:64]))


@bp.get("/prompts")
def prompts():
    """可编辑的对话 / 识图提示词。"""
    return ok(prompt_service.list_prompts())


@bp.put("/prompts/<key>")
def update_prompt(key: str):
    body = parse_body(PromptUpdateIn)
    return ok(prompt_service.update_prompt(key, body.content))


@bp.post("/prompts/<key>/reset")
def reset_prompt(key: str):
    return ok(prompt_service.reset_prompt(key))


@bp.get("/tools")
def tools():
    payload = []
    for item in get_tools():
        try:
            parameters = item.args_schema.model_json_schema() if item.args_schema else {}
        except Exception:
            parameters = {}
        payload.append(
            {
                "name": item.name,
                "description": item.description,
                "parameters": parameters,
            }
        )
    return ok(payload)
