"""房间服务。"""
from sqlalchemy import func

from app.extensions import db
from app.models import Container, Item, Room
from app.services import log_service
from app.utils.errors import ApiError


def _count_maps() -> tuple[dict[int, int], dict[int, int]]:
    item_counts = dict(
        db.session.query(Item.room_id, func.count(Item.id)).group_by(Item.room_id).all()
    )
    container_counts = dict(
        db.session.query(Container.room_id, func.count(Container.id))
        .group_by(Container.room_id)
        .all()
    )
    return item_counts, container_counts


def list_rooms() -> list[dict]:
    item_counts, container_counts = _count_maps()
    rooms = Room.query.order_by(Room.sort_order.asc(), Room.id.asc()).all()
    return [
        room.to_dict(
            item_count=item_counts.get(room.id, 0),
            container_count=container_counts.get(room.id, 0),
        )
        for room in rooms
    ]


def get_room(room_id: int) -> Room:
    room = db.session.get(Room, room_id)
    if not room:
        raise ApiError("房间不存在", 404)
    return room


def find_room_by_name(name: str) -> Room | None:
    return Room.query.filter_by(name=(name or "").strip()).first()


def resolve_room(room_id: int | None = None, name: str | None = None) -> Room:
    if room_id:
        return get_room(room_id)
    name = (name or "").strip()
    if not name:
        raise ApiError("需要提供房间名称或 ID")
    room = find_room_by_name(name)
    if not room:
        raise ApiError(f"房间「{name}」不存在", 404)
    return room


def create_room(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("房间名称不能为空")
    if find_room_by_name(name):
        raise ApiError(f"房间「{name}」已存在", 409)
    room = Room(
        name=name,
        description=data.get("description") or "",
        color=data.get("color") or "#2f7d6d",
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(room)
    db.session.flush()
    log_service.record("create", "room", room.id, {"name": name})
    db.session.commit()
    return room.to_dict(item_count=0, container_count=0)


def update_room(room_id: int, data: dict) -> dict:
    room = get_room(room_id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("房间名称不能为空")
        exists = Room.query.filter(Room.name == name, Room.id != room.id).first()
        if exists:
            raise ApiError(f"房间「{name}」已存在", 409)
        room.name = name
    if "description" in data:
        room.description = data.get("description") or ""
    if "color" in data:
        room.color = data.get("color") or room.color
    if "sort_order" in data:
        room.sort_order = int(data.get("sort_order") or 0)
    log_service.record("update", "room", room.id, data)
    db.session.commit()
    return room.to_dict()


def delete_room(room_id: int) -> None:
    room = get_room(room_id)
    container_count = Container.query.filter_by(room_id=room.id).count()
    item_count = Item.query.filter_by(room_id=room.id).count()
    if container_count or item_count:
        raise ApiError(
            f"房间内还有 {container_count} 个容器、{item_count} 件物品，请先清空后再删除",
            409,
        )
    log_service.record("delete", "room", room.id, {"name": room.name})
    db.session.delete(room)
    db.session.commit()
