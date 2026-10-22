"""操作日志服务。日志与业务写入处于同一事务，由调用方统一 commit。"""
from typing import Any

from flask import g, has_request_context

from app.extensions import db
from app.models import OperationLog
from app.utils.serialize import dumps


def current_source() -> str:
    if has_request_context():
        return getattr(g, "source", "api")
    return "system"


def record(
    action: str,
    entity_type: str = "",
    entity_id: int | None = None,
    detail: Any = None,
    source: str | None = None,
) -> OperationLog:
    log = OperationLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=dumps(detail if detail is not None else {}),
        source=source or current_source(),
    )
    db.session.add(log)
    return log


def list_logs(page: int = 1, page_size: int = 20, entity_type: str = "", source: str = ""):
    query = OperationLog.query
    if entity_type:
        query = query.filter(OperationLog.entity_type == entity_type)
    if source:
        query = query.filter(OperationLog.source == source)
    total = query.count()
    rows = (
        query.order_by(OperationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [row.to_dict() for row in rows], total
