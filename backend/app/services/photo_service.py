"""照片存储与文件管理。文件名使用 UUID，按年月分目录。"""
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Item, Photo
from app.services import log_service
from app.utils.errors import ApiError

FORMAT_MAP = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
    "GIF": ("gif", "image/gif"),
}


def upload_root() -> Path:
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_photo(photo_id: int) -> Photo:
    photo = db.session.get(Photo, photo_id)
    if not photo:
        raise ApiError("照片不存在", 404)
    return photo


def photo_abs_path(photo: Photo) -> Path:
    root = upload_root()
    path = (root / photo.file_path).resolve()
    if root not in path.parents and path != root:
        raise ApiError("非法的文件路径", 400)
    return path


def save_upload(file_storage, item_id: int | None = None) -> Photo:
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise ApiError("请选择要上传的图片")
    raw = file_storage.read()
    if not raw:
        raise ApiError("图片内容为空")
    max_bytes = int(current_app.config["MAX_CONTENT_LENGTH"])
    if len(raw) > max_bytes:
        raise ApiError(f"图片不能超过 {max_bytes // 1024 // 1024} MB", 413)

    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ApiError("无法识别该图片，请上传 JPG / PNG / WEBP / GIF") from exc

    fmt = (image.format or "").upper()
    if fmt not in FORMAT_MAP:
        raise ApiError("仅支持 JPG / PNG / WEBP / GIF 格式")
    ext, mime = FORMAT_MAP[fmt]
    width, height = image.size

    if item_id is not None:
        item = db.session.get(Item, int(item_id))
        if not item:
            raise ApiError("物品不存在", 404)

    now = datetime.now()
    rel_dir = Path(f"{now:%Y}") / f"{now:%m}"
    rel_path = rel_dir / f"{uuid.uuid4().hex}.{ext}"
    abs_dir = upload_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    (upload_root() / rel_path).write_bytes(raw)

    is_primary = False
    if item_id is not None:
        is_primary = Photo.query.filter_by(item_id=int(item_id)).count() == 0

    photo = Photo(
        item_id=int(item_id) if item_id is not None else None,
        file_path=str(rel_path).replace("\\", "/"),
        original_name=secure_filename(file_storage.filename or "")[:255],
        mime_type=mime,
        size=len(raw),
        width=width,
        height=height,
        is_primary=is_primary,
    )
    db.session.add(photo)
    db.session.flush()
    log_service.record(
        "upload",
        "photo",
        photo.id,
        {"item_id": photo.item_id, "file": photo.file_path, "size": photo.size},
    )
    db.session.commit()
    return photo


def list_photos(item_id: int | None = None) -> list[dict]:
    query = Photo.query
    if item_id is not None:
        query = query.filter_by(item_id=int(item_id))
    return [row.to_dict() for row in query.order_by(Photo.id.desc()).all()]


def attach_to_item(photo_id: int, item_id: int) -> dict:
    photo = get_photo(photo_id)
    item = db.session.get(Item, int(item_id))
    if not item:
        raise ApiError("物品不存在", 404)
    old_item_id = photo.item_id
    was_primary = photo.is_primary
    photo.item_id = item.id
    photo.is_primary = False
    db.session.flush()

    # 原物品失去主图时，提升另一张照片
    if was_primary and old_item_id and old_item_id != item.id:
        replacement = (
            Photo.query.filter_by(item_id=old_item_id)
            .order_by(Photo.id.asc())
            .first()
        )
        if replacement:
            replacement.is_primary = True

    # 目标物品还没有主图时，当前照片成为主图
    has_primary = Photo.query.filter(
        Photo.item_id == item.id,
        Photo.id != photo.id,
        Photo.is_primary.is_(True),
    ).count()
    if not has_primary:
        photo.is_primary = True

    log_service.record("attach", "photo", photo.id, {"item_id": item.id})
    db.session.commit()
    return photo.to_dict()


def set_primary(photo_id: int) -> dict:
    photo = get_photo(photo_id)
    if not photo.item_id:
        raise ApiError("照片尚未关联物品", 400)
    for row in Photo.query.filter_by(item_id=photo.item_id).all():
        row.is_primary = row.id == photo.id
    log_service.record("set_primary", "photo", photo.id, {"item_id": photo.item_id})
    db.session.commit()
    return photo.to_dict()


def delete_photo(photo_id: int) -> None:
    photo = get_photo(photo_id)
    item_id = photo.item_id
    was_primary = photo.is_primary
    rel_path = photo.file_path
    log_service.record("delete", "photo", photo.id, {"file": rel_path, "item_id": item_id})
    db.session.delete(photo)
    db.session.flush()
    if was_primary and item_id:
        replacement = (
            Photo.query.filter_by(item_id=item_id).order_by(Photo.id.asc()).first()
        )
        if replacement:
            replacement.is_primary = True
    db.session.commit()
    _unlink(rel_path)


def _unlink(rel_path: str) -> None:
    try:
        root = upload_root()
        target = (root / rel_path).resolve()
        if target.is_file() and (root in target.parents):
            target.unlink()
    except OSError:
        current_app.logger.warning("删除图片文件失败: %s", rel_path)


def delete_files(rel_paths: list[str]) -> None:
    for rel_path in rel_paths:
        _unlink(rel_path)
