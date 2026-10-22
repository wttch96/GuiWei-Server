"""全局搜索 API。"""
from flask import Blueprint, request

from app.services import search_service
from app.utils.responses import ok

bp = Blueprint("search", __name__, url_prefix="/api")


@bp.get("/search")
def search():
    query = request.args.get("q", "")
    return ok(search_service.search(query))
