"""房间 API。"""
from flask import Blueprint

from app.models import Container, Item
from app.schemas.common import parse_body
from app.schemas.storage import RoomIn, RoomUpdate
from app.services import container_service, item_service, room_service
from app.utils.responses import ok

bp = Blueprint("rooms", __name__, url_prefix="/api")


@bp.get("/rooms")
def list_rooms():
    return ok(room_service.list_rooms())


@bp.post("/rooms")
def create_room():
    body = parse_body(RoomIn)
    return ok(room_service.create_room(body.model_dump()), status=201)


@bp.get("/rooms/<int:room_id>")
def get_room(room_id: int):
    room = room_service.get_room(room_id)
    containers = container_service.list_containers(room_id)
    rows, _ = item_service.list_items({"room_id": room_id}, page=1, page_size=8)
    return ok(
        {
            "room": room.to_dict(
                item_count=Item.query.filter_by(room_id=room_id).count(),
                container_count=Container.query.filter_by(room_id=room_id).count(),
            ),
            "containers": containers,
            "recent_items": rows,
        }
    )


@bp.put("/rooms/<int:room_id>")
def update_room(room_id: int):
    body = parse_body(RoomUpdate)
    return ok(room_service.update_room(room_id, body.model_dump(exclude_unset=True)))


@bp.delete("/rooms/<int:room_id>")
def delete_room(room_id: int):
    room_service.delete_room(room_id)
    return ok({"deleted": True})


@bp.get("/rooms/<int:room_id>/tree")
def room_tree(room_id: int):
    room = room_service.get_room(room_id)
    return ok(
        {
            "room": room.to_dict(),
            "tree": container_service.list_tree(room_id),
            "containers": container_service.list_containers(room_id),
        }
    )
