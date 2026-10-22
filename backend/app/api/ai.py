"""AI 对话 / 状态 / 工具清单 / 会话历史。"""
from flask import Blueprint, g

from app.schemas.common import parse_body
from app.schemas.storage import ChatIn
from app.services import ai_service
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


@bp.get("/sessions/<session_id>/messages")
def session_messages(session_id: str):
    return ok(ai_service.get_messages(session_id[:64]))


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
