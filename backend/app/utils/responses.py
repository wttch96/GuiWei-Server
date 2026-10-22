"""统一响应格式：{code, message, data}。"""
from typing import Any

from flask import jsonify


def ok(data: Any = None, message: str = "ok", status: int = 200):
    return jsonify({"code": 0, "message": message, "data": data}), status


def paged(items: list, total: int, page: int, page_size: int, extra: dict | None = None):
    payload = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    if extra:
        payload.update(extra)
    return ok(payload)
