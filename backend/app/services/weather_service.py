"""天气服务：使用 Open-Meteo 免费接口，每小时把天津天气缓存到数据库。

Open-Meteo（https://open-meteo.com）无需 API Key，个人使用免费。
可用 .env 中的 WEATHER_* 覆盖城市、坐标与刷新间隔。
"""
import threading
import time
from datetime import datetime, timezone

import requests
from flask import current_app

from app.extensions import db
from app.models import WeatherSnapshot
from app.utils.errors import ApiError

# WMO 天气代码 → 中文描述
WEATHER_CODES = {
    0: "晴",
    1: "大部晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴小冰雹",
    99: "雷阵雨伴大冰雹",
}

DEFAULT_LATITUDE = 39.0842
DEFAULT_LONGITUDE = 117.2009
CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "weather_code,wind_speed_10m"
)
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_probability_max"


def describe_code(value) -> str:
    """把 WMO 天气代码转成中文描述。"""
    try:
        code = int(value)
    except (TypeError, ValueError):
        return "未知"
    return WEATHER_CODES.get(code, "未知")


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _city_name() -> str:
    return (current_app.config.get("WEATHER_CITY") or "天津").strip() or "天津"


def _first(values):
    return values[0] if isinstance(values, list) and values else None


def fetch() -> dict:
    """请求 Open-Meteo，返回归一化后的天气数据；失败时抛 ApiError。"""
    cfg = current_app.config
    params = {
        "latitude": cfg.get("WEATHER_LATITUDE", DEFAULT_LATITUDE),
        "longitude": cfg.get("WEATHER_LONGITUDE", DEFAULT_LONGITUDE),
        "current": CURRENT_FIELDS,
        "daily": DAILY_FIELDS,
        "timezone": "Asia/Shanghai",
        "forecast_days": 1,
    }
    try:
        response = requests.get(
            cfg.get("WEATHER_API_BASE"),
            params=params,
            timeout=int(cfg.get("WEATHER_TIMEOUT") or 10),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ApiError(f"天气接口请求失败：{str(exc)[:200]}", 502) from exc
    except ValueError as exc:
        raise ApiError("天气接口返回格式异常", 502) from exc
    if not isinstance(payload, dict):
        raise ApiError("天气接口返回格式异常", 502)

    current = payload.get("current") or {}
    daily = payload.get("daily") or {}
    code = _integer(current.get("weather_code"))
    return {
        "city": _city_name(),
        "weather": describe_code(code),
        "weather_code": code or 0,
        "temperature": _number(current.get("temperature_2m")),
        "apparent_temperature": _number(current.get("apparent_temperature")),
        "humidity": _integer(current.get("relative_humidity_2m")),
        "wind_speed": _number(current.get("wind_speed_10m")),
        "temp_max": _number(_first(daily.get("temperature_2m_max"))),
        "temp_min": _number(_first(daily.get("temperature_2m_min"))),
        "precipitation_probability": _integer(
            _first(daily.get("precipitation_probability_max"))
        ),
        "observed_at": str(current.get("time") or ""),
        "source": "open-meteo",
    }


def refresh(city: str | None = None) -> dict:
    """立即抓取一次并写入缓存（同一个城市只保留最新一条）。"""
    data = fetch()
    if city:
        data["city"] = city
    row = db.session.get(WeatherSnapshot, data["city"])
    if row is None:
        row = WeatherSnapshot(city=data["city"])
        db.session.add(row)
    for key in (
        "weather",
        "weather_code",
        "temperature",
        "apparent_temperature",
        "humidity",
        "wind_speed",
        "temp_max",
        "temp_min",
        "precipitation_probability",
        "observed_at",
        "source",
    ):
        setattr(row, key, data[key])
    db.session.commit()
    return row.to_dict()


def _empty(city: str) -> dict:
    return {
        "city": city,
        "weather": "",
        "weather_code": 0,
        "temperature": None,
        "apparent_temperature": None,
        "humidity": None,
        "wind_speed": None,
        "temp_max": None,
        "temp_min": None,
        "precipitation_probability": None,
        "observed_at": "",
        "source": "",
        "fetched_at": None,
        "stale": True,
        "available": False,
    }


def _age_seconds(row: WeatherSnapshot) -> float:
    updated = row.updated_at
    if updated is None:
        return float("inf")
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - updated).total_seconds()


def get_current(city: str | None = None, allow_fetch: bool = False) -> dict:
    """读取缓存；缓存过期且 allow_fetch 时现场刷新，刷新失败则回退旧数据。"""
    name = city or _city_name()
    row = db.session.get(WeatherSnapshot, name)
    ttl = max(1, int(current_app.config.get("WEATHER_REFRESH_MINUTES") or 60)) * 60

    if row is not None and _age_seconds(row) < ttl:
        return row.to_dict()
    if allow_fetch:
        try:
            return refresh(name)
        except ApiError:
            if row is None:
                raise
    if row is None:
        return _empty(name)
    data = row.to_dict()
    data["stale"] = True
    return data


def prompt_context() -> str:
    """生成注入 AI 提示词的天气文本；只用缓存，避免对话被外部请求阻塞。"""
    try:
        data = get_current(allow_fetch=False)
    except ApiError:
        return "天气：暂无数据（系统尚未获取到天气）。"
    if not data.get("available") or data.get("temperature") is None:
        return "天气：暂无数据（系统尚未获取到天气）。"

    parts = [f"{data['city']}当前{data['weather']}，气温 {data['temperature']:.0f}°C"]
    if data.get("apparent_temperature") is not None:
        parts.append(f"体感 {data['apparent_temperature']:.0f}°C")
    if data.get("temp_min") is not None and data.get("temp_max") is not None:
        parts.append(f"今日 {data['temp_min']:.0f}~{data['temp_max']:.0f}°C")
    if data.get("humidity") is not None:
        parts.append(f"湿度 {data['humidity']}%")
    if data.get("precipitation_probability") is not None:
        parts.append(f"降水概率 {data['precipitation_probability']}%")
    text = "，".join(parts)
    if data.get("observed_at"):
        text += f"（观测时间 {data['observed_at']}）"
    return text + "。"


_scheduler_lock = threading.Lock()
_scheduler_started = False


def start_scheduler(app) -> None:
    """启动每小时刷新天气的后台线程；测试环境不启动。"""
    global _scheduler_started
    if _scheduler_started or not app.config.get("WEATHER_ENABLED", True):
        return
    if app.config.get("TESTING"):
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    interval = max(300, int(app.config.get("WEATHER_REFRESH_MINUTES") or 60) * 60)

    def loop() -> None:
        while True:
            try:
                with app.app_context():
                    try:
                        refresh()
                    finally:
                        db.session.remove()
            except Exception:  # noqa: BLE001
                app.logger.warning("天气刷新失败，%s 秒后重试", interval, exc_info=True)
            time.sleep(interval)

    threading.Thread(target=loop, name="weather-refresh", daemon=True).start()
