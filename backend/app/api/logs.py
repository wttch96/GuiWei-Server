"""操作日志 API。"""
from flask import Blueprint, request

from app.schemas.common import int_arg
from app.services import log_service
from app.utils.responses import paged

bp = Blueprint("logs", __name__, url_prefix="/api")


@bp.get("/logs")
def list_logs():
    page = max(1, int_arg("page", 1) or 1)
    page_size = min(100, max(1, int_arg("page_size", 20) or 20))
    rows, total = log_service.list_logs(
        page=page,
        page_size=page_size,
        entity_type=request.args.get("entity_type", ""),
        source=request.args.get("source", ""),
    )
    return paged(rows, total, page, page_size)
