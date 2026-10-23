"""物品服务：创建、更新、移动、搜索、删除。"""
from sqlalchemy import or_

from app.extensions import db
from app.models import Category, ITEM_STATUSES, Item, Photo, Tag
from app.services import category_service, container_service, log_service, photo_service, room_service, tag_service
from app.utils.errors import ApiError

SORT_COLUMNS = {
    "created_at": Item.created_at,
    "updated_at": Item.updated_at,
    "name": Item.name,
    "quantity": Item.quantity,
}


def get_item(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if not item:
        raise ApiError("物品不存在", 404)
    return item


def find_items_by_name(name: str, limit: int = 10) -> list[Item]:
    term = (name or "").strip()
    if not term:
        return []
    return (
        Item.query.filter(Item.name.ilike(f"%{term}%"))
        .order_by(Item.updated_at.desc())
        .limit(limit)
        .all()
    )


def _validate_status(status: str | None) -> str:
    status = (status or "in_stock").strip()
    if status not in ITEM_STATUSES:
        raise ApiError(f"状态无效，可选值：{', '.join(ITEM_STATUSES)}", 422)
    return status


def _build_query(filters: dict):
    query = Item.query
    q = (filters.get("q") or "").strip()
    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                Item.name.ilike(term),
                Item.description.ilike(term),
                Item.ai_summary.ilike(term),
                Item.color_family.ilike(term),
                Item.category.has(Category.name.ilike(term)),
                Item.tags.any(Tag.name.ilike(term)),
            )
        )
    room_id = filters.get("room_id")
    if room_id:
        query = query.filter(Item.room_id == int(room_id))
    container_id = filters.get("container_id")
    if container_id:
        if filters.get("include_descendants", True):
            ids = container_service.subtree_ids(int(container_id))
            query = query.filter(Item.container_id.in_(ids))
        else:
            query = query.filter(Item.container_id == int(container_id))
    category_id = filters.get("category_id")
    if category_id:
        query = query.filter(Item.category_id == int(category_id))
    tag_id = filters.get("tag_id")
    if tag_id:
        query = query.filter(Item.tags.any(Tag.id == int(tag_id)))
    tag_name = (filters.get("tag_name") or "").strip()
    if tag_name:
        query = query.filter(Item.tags.any(Tag.name == tag_name))
    status = (filters.get("status") or "").strip()
    if status:
        query = query.filter(Item.status == status)
    color_family = (filters.get("color_family") or "").strip()
    if color_family:
        query = query.filter(Item.color_family == color_family)
    return query


def list_items(filters: dict, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    query = _build_query(filters)
    total = query.count()
    sort_key = filters.get("sort") or "updated_at"
    column = SORT_COLUMNS.get(sort_key, Item.updated_at)
    if (filters.get("order") or "desc").lower() == "asc":
        query = query.order_by(column.asc(), Item.id.asc())
    else:
        query = query.order_by(column.desc(), Item.id.desc())
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return [row.to_dict() for row in rows], total


def _resolve_category(data: dict) -> Category | None:
    if data.get("category_id"):
        return category_service.get_category(int(data["category_id"]))
    name = (data.get("category_name") or "").strip()
    if name:
        return category_service.get_or_create(name)
    return None


def _attach_photos(item: Item, photo_ids: list[int] | None) -> None:
    if not photo_ids:
        return
    photos = Photo.query.filter(Photo.id.in_([int(pid) for pid in photo_ids])).all()
    found = {photo.id for photo in photos}
    missing = [pid for pid in photo_ids if int(pid) not in found]
    if missing:
        raise ApiError(f"照片不存在: {missing}", 404)
    for photo in photos:
        if photo.item_id and photo.item_id != item.id:
            raise ApiError(f"照片 {photo.id} 已属于其它物品", 409)
        photo.item_id = item.id
    if not any(photo.is_primary for photo in item.photos):
        photos[0].is_primary = True


def create_item(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("物品名称不能为空")
    room = room_service.resolve_room(data.get("room_id"), data.get("room_name"))
    container = container_service.resolve_container(
        room.id, data.get("container_path"), data.get("container_id")
    )
    category = _resolve_category(data)
    tags = tag_service.resolve_tags(data.get("tag_ids"), data.get("tag_names"))
    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError) as exc:
        raise ApiError("数量必须是整数", 422) from exc
    if quantity < 0:
        raise ApiError("数量不能为负数", 422)

    item = Item(
        name=name,
        description=data.get("description") or "",
        ai_summary=data.get("ai_summary") or "",
        category_id=category.id if category else None,
        room_id=room.id,
        container_id=container.id if container else None,
        quantity=quantity,
        unit=(data.get("unit") or "件").strip() or "件",
        status=_validate_status(data.get("status")),
        color_family=(data.get("color_family") or "").strip()[:20],
        tags=tags,
    )
    db.session.add(item)
    db.session.flush()
    _attach_photos(item, data.get("photo_ids"))
    log_service.record(
        "create",
        "item",
        item.id,
        {"name": name, "location": item.location_path(), "tags": [t.name for t in tags]},
    )
    db.session.commit()
    db.session.refresh(item)
    return item.to_dict(detail=True)


def update_item(item_id: int, data: dict) -> dict:
    item = get_item(item_id)

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("物品名称不能为空")
        item.name = name
    if "description" in data:
        item.description = data.get("description") or ""
    if "ai_summary" in data:
        item.ai_summary = data.get("ai_summary") or ""
    if "quantity" in data:
        try:
            quantity = int(data.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise ApiError("数量必须是整数", 422) from exc
        if quantity < 0:
            raise ApiError("数量不能为负数", 422)
        item.quantity = quantity
    if "unit" in data:
        item.unit = (data.get("unit") or "件").strip() or "件"
    if "status" in data:
        item.status = _validate_status(data.get("status"))
    if "color_family" in data:
        item.color_family = (data.get("color_family") or "").strip()[:20]

    if "category_id" in data:
        if data.get("category_id") is None:
            item.category_id = None
        else:
            item.category_id = category_service.get_category(int(data["category_id"])).id
    elif (data.get("category_name") or "").strip():
        item.category_id = category_service.get_or_create(data["category_name"]).id

    # 位置更新：房间与容器需要保持一致
    room_touched = data.get("room_id") is not None or bool((data.get("room_name") or "").strip())
    target_room = item.room
    if room_touched:
        target_room = room_service.resolve_room(data.get("room_id"), data.get("room_name"))

    container_touched = "container_id" in data or "container_path" in data
    target_container = item.container
    if container_touched:
        container_id = data.get("container_id")
        container_path = data.get("container_path")
        if not container_id and not (container_path or "").strip():
            target_container = None
        else:
            target_container = container_service.resolve_container(
                target_room.id, container_path, container_id
            )
    elif target_room.id != item.room_id and item.container and item.container.room_id != target_room.id:
        raise ApiError("物品所在容器不属于新房间，请同时指定目标容器，或使用移动功能", 400)

    item.room_id = target_room.id
    item.container_id = target_container.id if target_container else None

    if "tag_ids" in data or "tag_names" in data:
        item.tags = tag_service.resolve_tags(data.get("tag_ids"), data.get("tag_names"))

    _attach_photos(item, data.get("photo_ids"))

    log_service.record("update", "item", item.id, data)
    db.session.commit()
    db.session.refresh(item)
    return item.to_dict(detail=True)


def move_item(item_id: int, room_id: int | None = None, room_name: str | None = None,
              container_id: int | None = None, container_path: str | None = None) -> dict:
    item = get_item(item_id)
    room = room_service.resolve_room(room_id, room_name)
    container = container_service.resolve_container(room.id, container_path, container_id)
    old_location = item.location_path()
    item.room_id = room.id
    item.container_id = container.id if container else None
    log_service.record(
        "move",
        "item",
        item.id,
        {"from": old_location, "to": item.location_path()},
    )
    db.session.commit()
    db.session.refresh(item)
    return item.to_dict(detail=True)


def set_item_tags(item_id: int, tag_ids: list[int] | None = None,
                  tag_names: list[str] | None = None) -> dict:
    item = get_item(item_id)
    item.tags = tag_service.resolve_tags(tag_ids, tag_names)
    log_service.record("set_tags", "item", item.id, {"tags": [t.name for t in item.tags]})
    db.session.commit()
    return item.to_dict(detail=True)


def delete_item(item_id: int) -> None:
    item = get_item(item_id)
    rel_paths = [photo.file_path for photo in item.photos]
    detail = {"name": item.name, "location": item.location_path()}
    log_service.record("delete", "item", item.id, detail)
    db.session.delete(item)
    db.session.commit()
    photo_service.delete_files(rel_paths)
