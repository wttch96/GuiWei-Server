"""AI 对话服务：LangChain ChatDeepSeek + 工具调用循环。

采用 LangChain Core 的 Tool / Message 原语手动驱动 tool-calling 循环，
不依赖 AgentExecutor 的版本差异，同时保留完整的工具调用轨迹。
"""
import json
import uuid
from datetime import date

from flask import current_app

from app.extensions import db
from app.models import AiMessage
from app.services import vision_service
from app.utils.errors import ApiError
from app.utils.serialize import dumps, loads

SYSTEM_PROMPT = """你是「归位」智能收纳助手，负责管理一个家庭的物品收纳数据库。

数据模型：
- 房间 Room → 容器 Container（可多级嵌套）→ 物品 Item
- 每个物品只属于一个分类 Category，可以有多个标签 Tag
- 位置统一表示为「房间 / 一级容器 / 二级容器」

工作规则：
1. 所有数据读取和修改都必须通过工具完成。禁止凭空编造 ID、房间名、容器名或物品。
2. 用户只给出名称时，先用查询工具解析出房间/容器/物品；名称不唯一时先询问用户。
3. 创建物品时尽量补全分类和标签；用户没说的信息不要随意编造。
4. 删除房间、容器、物品属于危险操作：只有用户明确表达删除意图时才执行，且 confirm 必须传 true。执行前先查询确认对象。
5. 可以连续调用多个工具完成多步操作。最后用简洁的中文总结做了什么、结果如何。
6. 用户说“把某物放到某处”时，优先使用 move_item；如果物品尚不存在，则用 create_item。
7. 不要向用户展示工具 JSON 原文，用自然语言汇报即可。
8. 今天是 {today}。"""


def _today() -> str:
    return date.today().isoformat()


def chat_configured() -> bool:
    return bool(current_app.config.get("DEEPSEEK_API_KEY"))


def status() -> dict:
    cfg = current_app.config
    return {
        "chat_configured": chat_configured(),
        "model": cfg.get("DEEPSEEK_MODEL"),
        "api_base": cfg.get("DEEPSEEK_API_BASE") if chat_configured() else None,
        "max_iterations": cfg.get("AI_MAX_ITERATIONS"),
        "vision": vision_service.status(),
    }


def _build_llm():
    """独立出来便于测试替换。"""
    from langchain_deepseek import ChatDeepSeek

    cfg = current_app.config
    common = {
        "model": cfg["DEEPSEEK_MODEL"],
        "api_key": cfg["DEEPSEEK_API_KEY"],
        "temperature": cfg["DEEPSEEK_TEMPERATURE"],
        "max_tokens": 2048,
        "timeout": 90,
    }
    try:
        return ChatDeepSeek(api_base=cfg["DEEPSEEK_API_BASE"], **common)
    except TypeError:
        # 兼容不同版本的参数名
        return ChatDeepSeek(base_url=cfg["DEEPSEEK_API_BASE"], **common)


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
            else:
                parts.append(str(part))
        return "\n".join(p for p in parts if p)
    return str(content)


def _load_history(session_id: str) -> list:
    from langchain_core.messages import AIMessage as LcAIMessage
    from langchain_core.messages import HumanMessage

    limit = int(current_app.config.get("AI_HISTORY_LIMIT") or 20)
    rows = (
        AiMessage.query.filter_by(session_id=session_id)
        .order_by(AiMessage.id.desc())
        .limit(limit)
        .all()
    )
    messages = []
    for row in reversed(rows):
        if row.role == "user":
            messages.append(HumanMessage(content=row.content))
        elif row.role == "assistant" and row.content:
            messages.append(LcAIMessage(content=row.content))
    return messages


def get_messages(session_id: str) -> list[dict]:
    rows = (
        AiMessage.query.filter_by(session_id=session_id)
        .order_by(AiMessage.id.asc())
        .all()
    )
    return [row.to_dict() for row in rows]


def chat(message: str, session_id: str | None = None) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    from app.tools import get_tools

    message = (message or "").strip()
    if not message:
        raise ApiError("消息不能为空")
    if not chat_configured():
        raise ApiError(
            "未配置 DEEPSEEK_API_KEY。请在 backend/.env 中填写后重启服务。", 503
        )
    if len(message) > 4000:
        raise ApiError("单条消息不能超过 4000 字", 422)

    session_id = (session_id or uuid.uuid4().hex)[:64]
    tools = get_tools()
    tool_map = {tool.name: tool for tool in tools}

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(today=_today())),
        *_load_history(session_id),
        HumanMessage(content=message),
    ]

    bound = _build_llm().bind_tools(tools)
    trace: list[dict] = []
    final = ""
    max_iterations = int(current_app.config.get("AI_MAX_ITERATIONS") or 8)

    try:
        for _ in range(max_iterations):
            ai_message = bound.invoke(messages)
            messages.append(ai_message)
            tool_calls = getattr(ai_message, "tool_calls", None) or []
            if not tool_calls:
                final = _content_to_text(ai_message.content)
                break
            for call in tool_calls:
                name = call.get("name") or ""
                args = call.get("args") or {}
                tool = tool_map.get(name)
                if not tool:
                    output = dumps({"ok": False, "error": f"未知工具：{name}"})
                else:
                    try:
                        output = tool.invoke(args)
                    except Exception as exc:  # 工具异常交还给模型自行处理
                        output = dumps({"ok": False, "error": str(exc)})
                    if not isinstance(output, str):
                        output = dumps(output)
                trace.append(
                    {"tool": name, "args": args, "result": loads(output, output)}
                )
                messages.append(
                    ToolMessage(
                        content=output,
                        tool_call_id=call.get("id") or f"call_{len(trace)}",
                        name=name,
                    )
                )
        else:
            final = "已达到最大工具调用轮数，操作可能没有全部完成。请拆分需求后重试。"
    except Exception as exc:
        raise ApiError(f"AI 调用失败：{str(exc)[:500]}", 502) from exc

    if not final:
        final = "已完成。"

    db.session.add(
        AiMessage(session_id=session_id, role="user", content=message, tool_trace="")
    )
    db.session.add(
        AiMessage(
            session_id=session_id,
            role="assistant",
            content=final,
            tool_trace=dumps(trace),
        )
    )
    db.session.commit()

    return {
        "session_id": session_id,
        "reply": final,
        "tool_calls": trace,
    }
