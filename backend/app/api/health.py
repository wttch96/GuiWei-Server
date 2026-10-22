"""健康检查（无需 Token）。"""
from flask import Blueprint
from sqlalchemy import text

from app.extensions import db
from app.models.base import utcnow
from app.utils.responses import ok
from app.utils.serialize import iso

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def check():
    database = "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    return ok({"status": "ok", "database": database, "time": iso(utcnow())})
