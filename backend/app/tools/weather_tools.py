"""天气工具：读取系统中缓存的当前天气。"""
from flask import current_app
from langchain_core.tools import tool

from app.services import weather_service
from app.tools.common import fail, ok
from app.utils.errors import ApiError


@tool
def get_weather(city: str = "") -> str:
    """查询当前天气与温度（默认天津）。用户询问天气、气温或穿衣建议时使用。

    Args:
        city: 城市名称；留空使用系统默认城市（天津）。系统只缓存了默认城市的天气。
    """
    default_city = (current_app.config.get("WEATHER_CITY") or "天津").strip() or "天津"
    target = (city or "").strip() or default_city
    if target != default_city:
        return fail(f"当前仅缓存了{default_city}的天气，暂不支持查询{target}", 404)
    try:
        return ok(weather_service.get_current(target, allow_fetch=True))
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:  # noqa: BLE001
        return fail(f"天气查询失败：{exc}", 500)
