"""照片存储与文件管理。文件名使用 UUID，按年月分目录。"""
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import joinedload
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
    # 临时裁切图（检测中间产物）不进入最近上传等普通列表
    query = Photo.query.filter(Photo.is_temp.is_(False))
    if item_id is not None:
        query = query.filter_by(item_id=int(item_id))
    return [row.to_dict() for row in query.order_by(Photo.id.desc()).all()]


def cleanup_temp_photos(ttl_minutes: int = 60) -> int:
    """删除超过保留时间且未入库的检测裁切图（文件 + 记录）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(ttl_minutes)))
    rows = (
        Photo.query.filter(
            Photo.is_temp.is_(True),
            Photo.item_id.is_(None),
            Photo.created_at < cutoff,
        )
        .all()
    )
    removed = 0
    for photo in rows:
        try:
            path = photo_abs_path(photo)
            if path.exists():
                path.unlink()
        except (OSError, ApiError):
            pass
        db.session.delete(photo)
        removed += 1
    if removed:
        db.session.commit()
    return removed


PHOTO_SORTS = {
    "newest": (Photo.created_at.desc(), Photo.id.desc()),
    "oldest": (Photo.created_at.asc(), Photo.id.asc()),
    "largest": (Photo.size.desc(), Photo.id.desc()),
    "smallest": (Photo.size.asc(), Photo.id.asc()),
}


def photo_summary() -> dict:
    """图片库总览：文件数量、占用空间、未关联数量（不含临时裁切图）。"""
    count, size = db.session.query(
        func.count(Photo.id), func.coalesce(func.sum(Photo.size), 0)
    ).filter(Photo.is_temp.is_(False)).one()
    orphan_count, orphan_size = (
        db.session.query(
            func.count(Photo.id), func.coalesce(func.sum(Photo.size), 0)
        )
        .filter(Photo.item_id.is_(None), Photo.is_temp.is_(False))
        .one()
    )
    return {
        "count": int(count),
        "size": int(size),
        "unattached_count": int(orphan_count),
        "unattached_size": int(orphan_size),
    }


def list_photo_page(
    q: str = "",
    status: str = "all",
    sort: str = "newest",
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[dict], int, dict]:
    """文件管理用的分页列表：附带物品名称，并省略识图全文。"""
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 24)))
    query = Photo.query.options(joinedload(Photo.item)).filter(
        Photo.is_temp.is_(False)
    )

    term = (q or "").strip()
    if term:
        query = query.filter(Photo.original_name.ilike(f"%{term}%"))
    status = (status or "all").strip()
    if status == "attached":
        query = query.filter(Photo.item_id.isnot(None))
    elif status == "unattached":
        query = query.filter(Photo.item_id.is_(None))

    total = query.count()
    order = PHOTO_SORTS.get((sort or "newest").strip(), PHOTO_SORTS["newest"])
    rows = query.order_by(*order).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for row in rows:
        data = row.to_dict()
        data.pop("ai_result", None)
        data["item_name"] = row.item.name if row.item else None
        items.append(data)
    return items, total, photo_summary()


def delete_photos(ids: list[int]) -> dict:
    """批量删除图片文件，并维护所属物品的主图。"""
    wanted = sorted({int(photo_id) for photo_id in ids})
    photos = Photo.query.filter(Photo.id.in_(wanted)).all()
    if not photos:
        raise ApiError("照片不存在", 404)

    found = {photo.id for photo in photos}
    rel_paths = [photo.file_path for photo in photos]
    primary_item_ids = {
        photo.item_id for photo in photos if photo.is_primary and photo.item_id
    }
    log_service.record(
        "batch_delete",
        "photo",
        None,
        {"ids": sorted(found), "count": len(photos)},
    )
    for photo in photos:
        db.session.delete(photo)
    db.session.flush()

    for item_id in primary_item_ids:
        replacement = (
            Photo.query.filter_by(item_id=item_id).order_by(Photo.id.asc()).first()
        )
        if replacement:
            replacement.is_primary = True

    db.session.commit()
    delete_files(rel_paths)
    return {"deleted": len(photos), "missing": sorted(set(wanted) - found)}


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
