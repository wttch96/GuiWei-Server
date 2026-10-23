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
from app.services import prompt_service, vision_service
from app.utils.errors import ApiError
from app.utils.serialize import dumps, iso, loads


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


def _empty_usage(include_steps: bool = False) -> dict:
    data = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
    }
    if include_steps:
        data["steps"] = []
    return data


def _merge_usage(target: dict, usage) -> dict:
    if not isinstance(usage, dict):
        return target
    for key in ("input_tokens", "output_tokens", "total_tokens", "llm_calls"):
        try:
            target[key] = target.get(key, 0) + int(usage.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return target


def _extract_usage(ai_message) -> dict:
    """从 LangChain 返回消息中读取 token 用量，兼容两种元数据位置。"""
    usage = getattr(ai_message, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    if input_tokens is None and output_tokens is None and total_tokens is None:
        metadata = getattr(ai_message, "response_metadata", None) or {}
        token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
        input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens"))
        output_tokens = token_usage.get(
            "completion_tokens", token_usage.get("output_tokens")
        )
        total_tokens = token_usage.get("total_tokens")

    def _int(value) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    prompt = _int(input_tokens)
    completion = _int(output_tokens)
    total = _int(total_tokens) or prompt + completion
    return {
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": total,
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
    payload = []
    for row in rows:
        data = row.to_dict()
        data["cards"] = (
            _extract_cards(data.get("tool_trace") or [])
            if row.role == "assistant"
            else []
        )
        payload.append(data)
    return payload


def session_usage(session_id: str) -> dict:
    rows = AiMessage.query.filter_by(
        session_id=session_id, role="assistant"
    ).all()
    total = _empty_usage()
    for row in rows:
        _merge_usage(total, loads(row.usage, None))
    return total


def list_sessions(limit: int = 100) -> list[dict]:
    """按会话聚合消息数、首条用户消息与 token 总量。"""
    rows = AiMessage.query.order_by(AiMessage.id.asc()).all()
    groups: dict[str, dict] = {}
    for row in rows:
        entry = groups.get(row.session_id)
        if entry is None:
            entry = {
                "session_id": row.session_id,
                "title": "",
                "preview": "",
                "created_at": iso(row.created_at),
                "updated_at": iso(row.updated_at),
                "message_count": 0,
                "user_messages": 0,
                "usage": _empty_usage(),
            }
            groups[row.session_id] = entry
        entry["message_count"] += 1
        entry["updated_at"] = iso(row.updated_at)
        entry["preview"] = (row.content or "").strip()[:80]
        if row.role == "user":
            entry["user_messages"] += 1
            if not entry["title"]:
                entry["title"] = (row.content or "").strip()[:60] or "未命名会话"
        elif row.role == "assistant":
            _merge_usage(entry["usage"], loads(row.usage, None))

    sessions = sorted(
        groups.values(), key=lambda item: item["updated_at"] or "", reverse=True
    )
    for entry in sessions:
        if not entry["title"]:
            entry["title"] = "未命名会话"
    return sessions[: max(1, int(limit or 100))]


def delete_session(session_id: str) -> dict:
    sid = (session_id or "")[:64]
    deleted = AiMessage.query.filter_by(session_id=sid).delete(
        synchronize_session=False
    )
    db.session.commit()
    if not deleted:
        raise ApiError("会话不存在", 404)
    return {"session_id": sid, "deleted": deleted}


# 这些工具的 data 直接就是一件物品；列表类工具则从 data.items 中提取。
ITEM_CARD_TOOLS = {"get_item", "create_item", "update_item", "move_item", "set_item_tags"}
ITEM_LIST_TOOLS = {"search_items", "global_search"}
ITEM_CARD_LIMIT = 8


def _item_card(item: dict) -> dict | None:
    """把物品序列化结果压缩成前端卡片需要的字段。"""
    if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
        return None
    category = item.get("category")
    photo = item.get("primary_photo")
    tags = item.get("tags") or []
    return {
        "id": item["id"],
        "name": item["name"],
        "description": (item.get("description") or item.get("ai_summary") or "").strip()[:200],
        "location_path": item.get("location_path") or "",
        "category": category.get("name") if isinstance(category, dict) else category,
        "tags": [
            tag.get("name") if isinstance(tag, dict) else str(tag) for tag in tags
        ][:8],
        "quantity": item.get("quantity", 1),
        "unit": item.get("unit", "件"),
        "status": item.get("status") or "",
        "status_label": item.get("status_label") or "",
        "primary_photo": photo if isinstance(photo, dict) else None,
    }


def _extract_cards(trace: list[dict]) -> list[dict]:
    """从工具调用结果中提取物品卡片，去重并限制数量。"""
    cards: list[dict] = []
    seen: set[int] = set()
    for call in trace or []:
        if not isinstance(call, dict):
            continue
        result = call.get("result")
        if not isinstance(result, dict) or not result.get("ok"):
            continue
        data = result.get("data")
        if not isinstance(data, dict):
            continue
        tool = call.get("tool")
        if tool in ITEM_CARD_TOOLS:
            raw_items = [data]
        elif tool in ITEM_LIST_TOOLS:
            raw_items = data.get("items") or []
        else:
            continue
        if not isinstance(raw_items, list):
            continue
        for raw in raw_items:
            card = _item_card(raw)
            if not card or card["id"] in seen:
                continue
            seen.add(card["id"])
            cards.append(card)
            if len(cards) >= ITEM_CARD_LIMIT:
                return cards
    return cards


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
        SystemMessage(
            content=prompt_service.get_chat_prompt().replace("{today}", _today())
        ),
        *_load_history(session_id),
        HumanMessage(content=message),
    ]

    bound = _build_llm().bind_tools(tools)
    trace: list[dict] = []
    final = ""
    max_iterations = int(current_app.config.get("AI_MAX_ITERATIONS") or 8)
    usage_total = _empty_usage(include_steps=True)

    try:
        for step in range(max_iterations):
            ai_message = bound.invoke(messages)
            step_usage = _extract_usage(ai_message)
            _merge_usage(usage_total, step_usage)
            usage_total["llm_calls"] += 1
            usage_total["steps"].append(dict(step_usage))
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
                    {
                        "tool": name,
                        "args": args,
                        "step": step + 1,
                        "usage": dict(step_usage),
                        "result": loads(output, output),
                    }
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
            usage=dumps(usage_total),
        )
    )
    db.session.commit()

    return {
        "session_id": session_id,
        "reply": final,
        "tool_calls": trace,
        "cards": _extract_cards(trace),
        "usage": usage_total,
        "session_usage": session_usage(session_id),
    }
