"""照片上传、下载、关联与 AI 识图。"""
from flask import Blueprint, current_app, request, send_file

from app.extensions import db
from app.schemas.common import int_arg, parse_body
from app.schemas.storage import (
    PhotoAnalyzeIn,
    PhotoAttachIn,
    PhotoBatchDeleteIn,
    PhotoSimilarIn,
)
from app.services import item_service, photo_service, similar_service, vision_service
from app.utils.errors import ApiError
from app.utils.responses import ok, paged
from app.utils.serialize import loads

bp = Blueprint("photos", __name__, url_prefix="/api")


@bp.post("/photos")
def upload_photo():
    upload = request.files.get("file")
    item_id = request.form.get("item_id")
    if item_id:
        try:
            item_id = int(item_id)
        except ValueError as exc:
            raise ApiError("item_id 必须是整数", 422) from exc
    else:
        item_id = None
    photo = photo_service.save_upload(upload, item_id=item_id)
    return ok(photo.to_dict(), status=201)


@bp.get("/photos")
def list_photos():
    item_id = int_arg("item_id")
    if item_id is not None:
        return ok(photo_service.list_photos(item_id))
    page = int_arg("page", 1) or 1
    page_size = int_arg("page_size", 24) or 24
    items, total, summary = photo_service.list_photo_page(
        q=request.args.get("q", ""),
        status=request.args.get("status", "all"),
        sort=request.args.get("sort", "newest"),
        page=page,
        page_size=page_size,
    )
    return paged(items, total, page, page_size, {"summary": summary})


@bp.get("/photos/<int:photo_id>")
def get_photo(photo_id: int):
    return ok(photo_service.get_photo(photo_id).to_dict())


@bp.get("/photos/<int:photo_id>/file")
def photo_file(photo_id: int):
    photo = photo_service.get_photo(photo_id)
    as_attachment = request.args.get("download") in {"1", "true", "yes"}
    response = send_file(
        photo_service.photo_abs_path(photo),
        mimetype=photo.mime_type,
        conditional=True,
        as_attachment=as_attachment,
        download_name=photo.original_name or f"photo-{photo.id}",
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.post("/photos/<int:photo_id>/attach")
def attach_photo(photo_id: int):
    body = parse_body(PhotoAttachIn)
    return ok(photo_service.attach_to_item(photo_id, body.item_id))


@bp.post("/photos/<int:photo_id>/primary")
def set_primary(photo_id: int):
    return ok(photo_service.set_primary(photo_id))


@bp.delete("/photos/<int:photo_id>")
def delete_photo(photo_id: int):
    photo_service.delete_photo(photo_id)
    return ok({"deleted": True})


@bp.post("/photos/batch-delete")
def batch_delete_photos():
    body = parse_body(PhotoBatchDeleteIn)
    return ok(photo_service.delete_photos(body.ids))


@bp.post("/photos/<int:photo_id>/analyze")
def analyze_photo(photo_id: int):
    body = parse_body(PhotoAnalyzeIn, optional=True)
    photo = photo_service.get_photo(photo_id)
    suggestion = vision_service.analyze_photo(photo)
    db.session.commit()  # 先保存识图结果，避免建物品失败时丢失

    # 描述匹配是增强功能，失败时不影响识图与入库
    try:
        similar_items = similar_service.find_similar_items(
            suggestion, exclude_item_id=photo.item_id
        )
    except Exception:  # noqa: BLE001
        current_app.logger.exception("相似物品匹配失败")
        similar_items = []

    created = None
    if body.create_item:
        if not body.room_id and not body.room_name:
            raise ApiError("识图成功；保存为物品需要提供 room_id 或 room_name", 422)
        name = (body.name or suggestion.get("name") or "").strip()
        if not name:
            raise ApiError("未能识别出物品名称，请手动填写后再保存", 422)
        data = {
            "name": name,
            "room_id": body.room_id,
            "room_name": body.room_name,
            "container_id": body.container_id,
            "category_id": body.category_id,
            "category_name": body.category_name or suggestion.get("category") or None,
            "tag_names": body.tags or suggestion.get("tags") or [],
            "description": body.description or suggestion.get("description") or "",
            "ai_summary": suggestion.get("description") or "",
            "quantity": body.quantity if body.quantity is not None else suggestion.get("quantity", 1),
            "photo_ids": [photo.id],
        }
        created = item_service.create_item(data)

    return ok(
        {
            "photo": photo.to_dict(),
            "suggestion": suggestion,
            "item": created,
            "similar_items": similar_items,
        }
    )


@bp.post("/photos/<int:photo_id>/similar")
def similar_photos(photo_id: int):
    """用照片已有的识图描述匹配相似物品，不重复调用视觉模型。"""
    body = parse_body(PhotoSimilarIn, optional=True)
    photo = photo_service.get_photo(photo_id)
    suggestion = loads(photo.ai_result, None)
    if not isinstance(suggestion, dict) or not suggestion:
        raise ApiError("请先执行 AI 识图，再查找相似物品", 422)
    items = similar_service.find_similar_items(
        suggestion, limit=body.limit, exclude_item_id=photo.item_id
    )
    return ok({"suggestion": suggestion, "items": items})
