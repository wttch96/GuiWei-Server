"""统计 API。"""
from flask import Blueprint

from app.services import stats_service
from app.utils.responses import ok

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats/overview")
def overview():
    return ok(stats_service.overview())
