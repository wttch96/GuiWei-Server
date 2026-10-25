"""多物品检测与裁切：基于 YOLOE / YOLO-World 开放词汇模型。

- 默认使用 YOLOE 分割模型：既能用英文提示词识别物品，又能输出实例 mask。
- mask 只用于生成一张白底「识别图」给视觉模型；保存/展示的缩略图始终是原图直接裁切。
- 该能力依赖可选包 ultralytics（见 backend/requirements-yolo.txt）。
  未安装时 status() 返回 installed=False，检测接口返回 503 并给出安装提示，
  不影响单物品识图等其它功能。
"""
import importlib.util
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import current_app
from PIL import Image, ImageDraw

from app.extensions import db
from app.models import Photo
from app.services import log_service, photo_service
from app.utils.errors import ApiError

# 进程内缓存模型，避免每次检测都重新加载权重
_model = None
_model_name: str | None = None

# 过滤阈值：过小的检测框通常是误检
MIN_AREA_RATIO = 0.0003  # 小于原图万分之三
MIN_SIDE = 12            # 原始检测框的绝对最小边长（像素）

# YOLO-World / YOLOE 的类别提示词必须是英文；界面展示时映射成中文。
# 未收录的类别会原样显示英文。
LABEL_ZH = {
    "bottle": "瓶子",
    "jar": "罐子",
    "can": "罐头/易拉罐",
    "box": "盒子",
    "container": "收纳容器",
    "basket": "篮子",
    "bag": "包",
    "cup": "杯子",
    "bowl": "碗",
    "plate": "盘子",
    "book": "书",
    "notebook": "笔记本",
    "pen": "笔",
    "scissors": "剪刀",
    "tape": "胶带",
    "remote": "遥控器",
    "cell phone": "手机",
    "charger": "充电器",
    "cable": "线缆",
    "power bank": "充电宝",
    "headphones": "耳机",
    "key": "钥匙",
    "wallet": "钱包",
    "umbrella": "雨伞",
    "glasses": "眼镜",
    "watch": "手表",
    "towel": "毛巾",
    "clothes": "衣物",
    "shoe": "鞋子",
    "hat": "帽子",
    "toy": "玩具",
    "medicine bottle": "药瓶",
    "medicine box": "药盒",
    "pill": "药片",
    "blister pack": "药板",
    "band-aid": "创可贴",
    "ointment tube": "药膏",
    "cotton swab": "棉签",
    "thermometer": "体温计",
    "face mask": "口罩",
    "first aid kit": "急救箱",
    "cosmetic bottle": "化妆品瓶",
    "perfume": "香水",
    "toothbrush": "牙刷",
    "toothpaste": "牙膏",
    "soap": "香皂",
    "shampoo": "洗发水",
    "tissue": "纸巾",
    "snack": "零食",
    "chopsticks": "筷子",
    "spoon": "勺子",
    "fork": "叉子",
    "knife": "刀",
    "keyboard": "键盘",
    "computer mouse": "鼠标",
    "computer monitor": "显示器",
    "television": "电视",
    "laptop": "笔记本电脑",
    "tablet": "平板电脑",
    "speaker": "音箱",
    "printer": "打印机",
    "router": "路由器",
    "game controller": "游戏手柄",
    "camera": "相机",
    "microphone": "麦克风",
    "tripod": "三脚架",
    "usb drive": "优盘",
    "external hard drive": "移动硬盘",
    "power strip": "插线板",
    "stapler": "订书机",
    "ruler": "尺子",
    "glue": "胶水",
    "calculator": "计算器",
    "desk lamp": "台灯",
    "electric fan": "风扇",
    "clock": "时钟",
    "picture frame": "相框",
    "vase": "花瓶",
    "candle": "蜡烛",
    "lighter": "打火机",
    "battery": "电池",
    "flashlight": "手电筒",
    "hairdryer": "吹风机",
    "clothes iron": "熨斗",
    "razor": "剃须刀",
    "shaving cream": "剃须膏",
    "comb": "梳子",
    "hairbrush": "发刷",
    "body wash": "沐浴露",
    "face wash": "洗面奶",
    "hand sanitizer": "洗手液",
    "mouthwash": "漱口水",
    "dental floss": "牙线",
    "water flosser": "冲牙器",
    "deodorant": "除臭剂",
    "cotton pad": "化妆棉",
    "nail clippers": "指甲刀",
    "tweezers": "镊子",
    "makeup brush": "化妆刷",
    "lipstick": "口红",
    "sunscreen": "防晒霜",
    "mirror": "镜子",
    "bathroom scale": "体重秤",
    "loofah": "浴球",
    "soap dish": "皂盒",
    "shower cap": "浴帽",
    "toilet paper": "卫生纸",
    "washcloth": "洗脸巾",
    "toothbrush holder": "牙刷架",
    "cosmetic bag": "化妆包",
}


def label_zh(label: str) -> str:
    return LABEL_ZH.get((label or "").strip().lower(), label)


def class_list() -> list[str]:
    """从配置中解析英文类别提示词（逗号分隔）。"""
    raw = str(current_app.config.get("YOLO_CLASSES") or "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def status() -> dict:
    """检测能力状态：是否安装依赖、当前模型、是否支持 mask 等，供前端展示。"""
    cfg = current_app.config
    model = str(cfg.get("YOLO_MODEL") or "")
    return {
        "installed": importlib.util.find_spec("ultralytics") is not None,
        "model": model,
        "segmentation": "seg" in model.lower() or "yoloe" in model.lower(),
        "use_mask": bool(cfg.get("YOLO_USE_MASK")),
        "mask_cutout": bool(cfg.get("YOLO_MASK_CUTOUT")),
        "classes": class_list(),
        "confidence": cfg.get("YOLO_CONFIDENCE"),
        "min_crop_side": cfg.get("YOLO_MIN_CROP_SIDE"),
    }


def weights_dir() -> Path:
    """模型与 CLIP 权重的统一缓存目录（默认 backend/weights）。"""
    path = Path(current_app.config.get("YOLO_WEIGHTS_DIR") or "weights").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _download(url: str, target: Path) -> None:
    """流式下载到临时文件，成功后再原子替换，避免半截文件被当作有效权重。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    temporary = target.with_suffix(target.suffix + ".part")
    with temporary.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                handle.write(chunk)
    temporary.replace(target)


# YOLOE 使用 Apple MobileCLIP 作为文本编码器（约 572MB）
MOBILECLIP_URL = (
    "https://github.com/ultralytics/assets/releases/download/v8.4.0/mobileclip_blt.ts"
)


def ensure_mobileclip_weights() -> Path:
    """预下载 YOLOE 的 MobileCLIP 文本编码器权重到 YOLO_WEIGHTS_DIR。

    ultralytics 默认会把权重下载到当前工作目录；这里统一收敛到 weights 目录，
    并通过 SETTINGS["weights_dir"] 让后续加载直接命中缓存。
    """
    target = weights_dir() / "mobileclip_blt.ts"
    if not target.exists():
        try:
            _download(MOBILECLIP_URL, target)
        except Exception as exc:
            raise ApiError(
                f"MobileCLIP 权重下载失败：{str(exc)[:160]}。"
                f"可手动下载 {MOBILECLIP_URL} 到 {target}",
                503,
            ) from exc
    return target


def ensure_clip_weights() -> Path:
    """预下载 CLIP 文本编码器权重。

    ultralytics 内部用 urllib 下载，遇到企业代理/自签证书会失败；
    统一改用 requests（certifi 证书链）下载到 YOLO_WEIGHTS_DIR/clip。
    """
    try:
        import clip.clip as clip_module
    except ImportError as exc:
        raise ApiError(
            "缺少 CLIP 文本编码器，请重新执行：pip install -r requirements-yolo.txt",
            503,
        ) from exc

    url = clip_module._MODELS.get("ViT-B/32")  # noqa: SLF001
    if not url:
        raise ApiError("当前 CLIP 版本不支持 ViT-B/32", 503)
    target = weights_dir() / "clip" / Path(urlparse(url).path).name
    if not target.exists():
        try:
            _download(url, target)
        except Exception as exc:
            raise ApiError(
                f"CLIP 权重下载失败：{str(exc)[:160]}。"
                f"可手动下载 {url} 到 {target}",
                503,
            ) from exc
    return target


def _load_model():
    """懒加载并缓存模型；YOLOE 走开放词汇 + 文本编码器，YOLO-World 走兼容路径。"""
    global _model, _model_name
    name = current_app.config.get("YOLO_MODEL") or "yoloe-11l-seg.pt"
    if _model is not None and _model_name == name:
        return _model
    try:
        from ultralytics import YOLOE, YOLOWorld
        from ultralytics.nn import text_model
    except ImportError as exc:
        raise ApiError(
            "未安装 ultralytics，无法进行多物品检测。"
            "请在后端执行：pip install -r requirements-yolo.txt",
            503,
        ) from exc

    directory = weights_dir()
    # 文本编码器权重统一放到 YOLO_WEIGHTS_DIR，避免下载到当前工作目录
    text_model.WEIGHTS_DIR = directory
    try:
        from ultralytics.utils import SETTINGS

        SETTINGS["weights_dir"] = str(directory)
    except Exception:  # noqa: BLE001  老版本 ultralytics 可能没有该配置
        pass

    model_path = Path(name)
    if not model_path.is_absolute():
        model_path = directory / model_path.name
    classes = class_list()
    is_seg = "yoloe" in name.lower()
    # YOLOE 用 MobileCLIP；YOLO-World 用 OpenAI CLIP ViT-B/32
    encoder_path = ensure_mobileclip_weights() if is_seg else ensure_clip_weights()
    try:
        if is_seg:
            # YOLOE：开放词汇 + 实例分割，mask 只用于生成识别图
            model = YOLOE(str(model_path))
            if classes:
                model.set_classes(classes, model.get_text_pe(classes))
        else:
            model = YOLOWorld(str(model_path))
            if classes:
                model.set_classes(classes)
    except Exception as exc:  # 权重缺失、下载失败、文本类别初始化失败等
        raise ApiError(
            f"YOLO 模型初始化失败：{str(exc)[:200]}（文本编码器权重：{encoder_path}）",
            503,
        ) from exc
    _model = model
    _model_name = name
    return model


def _device() -> str:
    """未显式配置时优先使用 Apple Silicon 的 MPS。"""
    configured = (current_app.config.get("YOLO_DEVICE") or "").strip()
    if configured:
        return configured
    try:
        import torch

        return "mps" if torch.backends.mps.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def _crop_box(
    box: list[float], width: int, height: int, padding: float
) -> tuple[int, int, int, int]:
    """按比例向四周外扩检测框，并裁剪到图片边界内。"""
    x1, y1, x2, y2 = box
    pad = padding * max(x2 - x1, y2 - y1)
    return (
        max(0, int(round(x1 - pad))),
        max(0, int(round(y1 - pad))),
        min(width, int(round(x2 + pad))),
        min(height, int(round(y2 + pad))),
    )


def _iou(a: list[float], b: list[float]) -> float:
    """两个 xyxy 框的交并比，用于跨类别去重。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _apply_cutout(
    crop: Image.Image, polygon: list[tuple[float, float]], crop_box: tuple[int, int, int, int]
) -> Image.Image:
    """按 mask 轮廓把物品抠到白底上，去掉框内的其它杂物。"""
    if len(polygon) < 3:
        return crop
    offset_x, offset_y = crop_box[0], crop_box[1]
    mask = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([(x - offset_x, y - offset_y) for x, y in polygon], fill=255)
    background = Image.new("RGB", crop.size, (255, 255, 255))
    return Image.composite(crop, background, mask)


def _save_crop(crop: Image.Image, label: str) -> Photo:
    """把裁切图保存为临时照片（is_temp=True），未入库时不会出现在图片库并会被清理。"""
    now = datetime.now()
    rel_dir = Path(f"{now:%Y}") / f"{now:%m}"
    rel_path = rel_dir / f"{uuid.uuid4().hex}.jpg"
    root = photo_service.upload_root()
    (root / rel_dir).mkdir(parents=True, exist_ok=True)
    abs_path = root / rel_path
    crop.save(abs_path, format="JPEG", quality=88)

    photo = Photo(
        item_id=None,
        file_path=str(rel_path).replace("\\", "/"),
        original_name=f"{label}.jpg"[:255],
        mime_type="image/jpeg",
        size=abs_path.stat().st_size,
        width=crop.width,
        height=crop.height,
        is_temp=True,
    )
    db.session.add(photo)
    db.session.flush()
    return photo


def detect_photo(photo: Photo) -> list[dict]:
    """检测照片中的多件物品，返回保存用裁切图与识别用抠图。

    返回结构：每件物品包含 label / confidence / box / photo（原图直接裁切）
    以及 analysis_photo（白底 mask 抠图，可能为 None）。
    """
    cfg = current_app.config
    # 先清理上一轮未入库的临时裁切图，避免图片库和磁盘堆积
    photo_service.cleanup_temp_photos(int(cfg.get("YOLO_TEMP_TTL_MINUTES") or 60))
    model = _load_model()
    image_path = photo_service.photo_abs_path(photo)

    predict_args = {
        "source": str(image_path),
        "conf": float(cfg.get("YOLO_CONFIDENCE") or 0.35),
        "iou": float(cfg.get("YOLO_IOU") or 0.45),
        "imgsz": int(cfg.get("YOLO_IMAGE_SIZE") or 1280),
        "agnostic_nms": bool(cfg.get("YOLO_AGNOSTIC_NMS")),
        "device": _device(),
        "verbose": False,
    }

    try:
        results = model.predict(**predict_args)
    except Exception as exc:
        raise ApiError(f"物品检测失败：{str(exc)[:200]}", 502) from exc
    if not results:
        return []

    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    names = getattr(result, "names", None) or getattr(model, "names", {})
    use_mask = bool(cfg.get("YOLO_USE_MASK"))
    masks = getattr(result, "masks", None) if use_mask else None
    polygons = getattr(masks, "xy", None) if masks is not None else None
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    width, height = image.size
    min_crop_side = max(MIN_SIDE, int(cfg.get("YOLO_MIN_CROP_SIDE") or 64))
    padding = float(cfg.get("YOLO_CROP_PADDING") or 0.06)
    cutout = use_mask and bool(cfg.get("YOLO_MASK_CUTOUT"))

    candidates: list[dict] = []
    for index in range(len(boxes)):
        box = boxes[index]
        xyxy = [float(value) for value in box.xyxy[0].tolist()]
        score = float(box.conf[0])
        class_id = int(box.cls[0])
        label = names.get(class_id) if isinstance(names, dict) else names[class_id]
        x1, y1, x2, y2 = xyxy
        if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
            continue

        # 分割模型：mask 只用于生成「识别图」；保存/展示始终用检测框直接裁切的原图
        polygon = None
        if polygons is not None and index < len(polygons):
            points = polygons[index]
            if points is not None and len(points) >= 3:
                polygon = [(float(p[0]), float(p[1])) for p in points]

        crop_box = _crop_box(xyxy, width, height, padding)
        crop_width = crop_box[2] - crop_box[0]
        crop_height = crop_box[3] - crop_box[1]
        # 切割后像素太低（短边不足 min_crop_side）的物品直接忽略
        if crop_width < min_crop_side or crop_height < min_crop_side:
            continue
        if (crop_width * crop_height) / max(1, width * height) < MIN_AREA_RATIO:
            continue

        display_crop = image.crop(crop_box)
        analysis_crop = None
        if cutout and polygon:
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            mask_box = _crop_box([min(xs), min(ys), max(xs), max(ys)], width, height, padding)
            if (
                mask_box[2] - mask_box[0] >= min_crop_side
                and mask_box[3] - mask_box[1] >= min_crop_side
            ):
                analysis_crop = _apply_cutout(image.crop(mask_box), polygon, mask_box)

        candidates.append(
            {
                "label": str(label),
                "label_zh": label_zh(str(label)),
                "confidence": round(score, 3),
                "box": [round(value, 1) for value in xyxy],
                "xyxy": xyxy,
                "crop": display_crop,
                "analysis_crop": analysis_crop,
            }
        )

    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    # 跨类别去掉几乎完全重合的框（如 jar/can/bottle 同时命中同一物体），
    # 只保留置信度最高的一条；相邻但不重合的物品不受影响。
    deduped: list[dict] = []
    for candidate in candidates:
        if any(_iou(candidate["xyxy"], kept["xyxy"]) > 0.85 for kept in deduped):
            continue
        deduped.append(candidate)
    limit = max(1, int(cfg.get("YOLO_MAX_OBJECTS") or 12))
    candidates = deduped[:limit]

    detections = []
    for candidate in candidates:
        crop_photo = _save_crop(candidate["crop"], candidate["label"])
        analysis_photo = None
        if candidate.get("analysis_crop") is not None:
            analysis_photo = _save_crop(candidate["analysis_crop"], candidate["label"])
        detections.append(
            {
                "label": candidate["label"],
                "label_zh": candidate["label_zh"],
                "confidence": candidate["confidence"],
                "box": candidate["box"],
                "photo": crop_photo.to_dict(),
                # 仅用于视觉识别的白底抠图；不入库，识别后删除
                "analysis_photo": analysis_photo.to_dict() if analysis_photo else None,
            }
        )

    log_service.record(
        "detect",
        "photo",
        photo.id,
        {"count": len(detections), "labels": [item["label"] for item in detections]},
    )
    db.session.commit()
    return detections
