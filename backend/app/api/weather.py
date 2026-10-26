"""天气缓存查询。"""
from flask import Blueprint, request

from app.services import weather_service
from app.utils.responses import ok

bp = Blueprint("weather", __name__, url_prefix="/api")


@bp.get("/weather")
def get_weather():
    """读取缓存的天气；?refresh=1 会立即请求外部接口刷新。"""
    force = request.args.get("refresh") in {"1", "true", "yes"}
    return ok(weather_service.get_current(allow_fetch=force))
