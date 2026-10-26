"""天气缓存：每个城市保存最近一次抓取结果。

系统每小时刷新一次，供 AI 提示词注入与前端查询使用，避免每次对话都请求外部接口。
"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso


class WeatherSnapshot(db.Model, TimestampMixin):
    __tablename__ = "weather_snapshots"

    city = db.Column(db.String(40), primary_key=True)
    weather = db.Column(db.String(40), default="", nullable=False)
    weather_code = db.Column(db.Integer, default=0, nullable=False)
    temperature = db.Column(db.Float, nullable=True)
    apparent_temperature = db.Column(db.Float, nullable=True)
    humidity = db.Column(db.Integer, nullable=True)
    wind_speed = db.Column(db.Float, nullable=True)
    temp_max = db.Column(db.Float, nullable=True)
    temp_min = db.Column(db.Float, nullable=True)
    precipitation_probability = db.Column(db.Integer, nullable=True)
    observed_at = db.Column(db.String(32), default="", nullable=False)
    source = db.Column(db.String(120), default="", nullable=False)

    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "weather": self.weather or "",
            "weather_code": self.weather_code or 0,
            "temperature": self.temperature,
            "apparent_temperature": self.apparent_temperature,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "temp_max": self.temp_max,
            "temp_min": self.temp_min,
            "precipitation_probability": self.precipitation_probability,
            "observed_at": self.observed_at or "",
            "source": self.source or "",
            "fetched_at": iso(self.updated_at),
            "stale": False,
            "available": True,
        }
