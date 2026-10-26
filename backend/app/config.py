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
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    DEEPSEEK_TEMPERATURE = _float("DEEPSEEK_TEMPERATURE", 0)
    AI_MAX_ITERATIONS = _int("AI_MAX_ITERATIONS", 8)
    AI_HISTORY_LIMIT = 20

    # 视觉识图（DeepSeek 多模态，OpenAI 兼容 /chat/completions）
    # deepseek-flash 支持图片输入，默认复用对话的 API Base 与 Key；
    # 如需其它兼容网关，可用 VISION_* 单独覆盖。
    VISION_API_BASE = os.getenv("VISION_API_BASE") or DEEPSEEK_API_BASE
    VISION_API_KEY = os.getenv("VISION_API_KEY") or DEEPSEEK_API_KEY
    VISION_MODEL = os.getenv("VISION_MODEL") or "deepseek-flash"
    VISION_TIMEOUT = _int("VISION_TIMEOUT", 120)

    # 多物品检测（可选，需要安装 requirements-yolo.txt）
    # 默认使用 YOLOE 开放词汇分割模型：既有类别提示，又能输出实例 mask 用于精确裁切。
    # 注意：提示词需要英文，中文名称只在界面展示时映射。
    YOLO_MODEL = os.getenv("YOLO_MODEL", "yoloe-11l-seg.pt")
    YOLO_WEIGHTS_DIR = os.getenv("YOLO_WEIGHTS_DIR") or str(BASE_DIR / "weights")
    # 开放词汇类别：默认覆盖常见家居/收纳/洗漱物品，可在 .env 中按需增删。
    # 顺序不影响结果；提示词越贴近实际物品，检出越稳。
    YOLO_CLASSES = os.getenv(
        "YOLO_CLASSES",
        # 容器、厨房与餐具
        "bottle, jar, can, box, container, basket, bag, cup, bowl, plate, "
        # 文具与桌面小物
        "book, notebook, pen, scissors, tape, stapler, ruler, glue, calculator, "
        # 数码与线材
        "remote, cell phone, tablet, laptop, keyboard, computer mouse, "
        "computer monitor, television, speaker, printer, router, game controller, "
        "camera, microphone, tripod, usb drive, external hard drive, power strip, "
        "charger, cable, power bank, headphones, "
        # 随身与衣物
        "key, wallet, umbrella, glasses, watch, towel, clothes, shoe, hat, toy, "
        # 药品与健康
        "medicine bottle, medicine box, pill, blister pack, band-aid, "
        "ointment tube, cotton swab, thermometer, face mask, first aid kit, "
        # 洗护与美妆
        "cosmetic bottle, perfume, toothbrush, toothpaste, soap, shampoo, "
        "razor, shaving cream, comb, hairbrush, body wash, face wash, "
        "hand sanitizer, mouthwash, dental floss, water flosser, deodorant, "
        "cotton pad, nail clippers, tweezers, makeup brush, lipstick, sunscreen, "
        # 家居日用
        "tissue, snack, chopsticks, spoon, fork, knife, "
        "desk lamp, electric fan, clock, picture frame, vase, candle, lighter, "
        "battery, flashlight, hairdryer, clothes iron, "
        "mirror, bathroom scale, loofah, soap dish, shower cap, toilet paper, "
        "washcloth, toothbrush holder, cosmetic bag",
    )
    YOLO_CONFIDENCE = _float("YOLO_CONFIDENCE", 0.35)
    YOLO_IOU = _float("YOLO_IOU", 0.45)
    # 多物品照片通常物品小且密集，640 会丢失细节；1280 在 CPU 上仍可接受
    YOLO_IMAGE_SIZE = _int("YOLO_IMAGE_SIZE", 1280)
    # 裁切向外扩展比例，避免切掉物体边缘
    YOLO_CROP_PADDING = _float("YOLO_CROP_PADDING", 0.06)
    YOLO_MAX_OBJECTS = _int("YOLO_MAX_OBJECTS", 12)
    # 裁切后短边小于该像素的物品直接忽略，避免低清小图入库
    YOLO_MIN_CROP_SIDE = _int("YOLO_MIN_CROP_SIDE", 64)
    # 跨类别 NMS：jar/can/bottle 等语义重叠时去重；相邻物品较多时建议关闭
    YOLO_AGNOSTIC_NMS = _bool("YOLO_AGNOSTIC_NMS", False)
    # 未入库的检测裁切图保留时间（分钟），过期自动删除
    YOLO_TEMP_TTL_MINUTES = _int("YOLO_TEMP_TTL_MINUTES", 60)
    # mask 只用于生成「识别图」；保存/展示的缩略图始终是原图直接裁切
    YOLO_USE_MASK = _bool("YOLO_USE_MASK", True)
    # 识别图是否按 mask 抠成白底（关闭后识别也用原图裁切）
    YOLO_MASK_CUTOUT = _bool("YOLO_MASK_CUTOUT", True)
    # 留空时自动使用 mps（Apple Silicon）或 cpu
    YOLO_DEVICE = os.getenv("YOLO_DEVICE", "")

    # 天气（Open-Meteo 免费接口，无需 API Key）
    WEATHER_ENABLED = _bool("WEATHER_ENABLED", True)
    WEATHER_CITY = os.getenv("WEATHER_CITY", "天津")
    WEATHER_LATITUDE = _float("WEATHER_LATITUDE", 39.0842)
    WEATHER_LONGITUDE = _float("WEATHER_LONGITUDE", 117.2009)
    WEATHER_REFRESH_MINUTES = _int("WEATHER_REFRESH_MINUTES", 60)
    WEATHER_TIMEOUT = _int("WEATHER_TIMEOUT", 10)
    WEATHER_API_BASE = os.getenv(
        "WEATHER_API_BASE", "https://api.open-meteo.com/v1/forecast"
    )

    # 其它
    AUTO_CREATE_DB = _bool("AUTO_CREATE_DB", True)
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", False)
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = False
