"""集中配置。所有配置均可用环境变量覆盖（见 .env.example）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # Flask / JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "guiwei-dev-secret-change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_HOURS = _int("JWT_EXPIRES_HOURS", 168)

    # 数据库：留空时由 create_app 写入 instance/guiwei.db
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 文件
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = _int("MAX_UPLOAD_MB", 20) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
    THUMBNAIL_MAX_SIDE = 512

    # 跨域
    CORS_ORIGINS = [
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if item.strip()
    ]

    # 管理员
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    AUTO_BOOTSTRAP_ADMIN = _bool("AUTO_BOOTSTRAP_ADMIN", True)

    # DeepSeek 对话
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_TEMPERATURE = _float("DEEPSEEK_TEMPERATURE", 0)
    AI_MAX_ITERATIONS = _int("AI_MAX_ITERATIONS", 8)
    AI_HISTORY_LIMIT = 20

    # 视觉模型（OpenAI 兼容 /chat/completions）
    VISION_API_BASE = os.getenv("VISION_API_BASE", "https://api.deepseek.com/v1")
    VISION_API_KEY = os.getenv("VISION_API_KEY", "") or DEEPSEEK_API_KEY
    VISION_MODEL = os.getenv("VISION_MODEL", "")
    VISION_TIMEOUT = _int("VISION_TIMEOUT", 120)

    # 其它
    AUTO_CREATE_DB = _bool("AUTO_CREATE_DB", True)
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", False)
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = False
