"""物品 API。"""
from flask import Blueprint, request

from app.schemas.common import bool_arg, int_arg, parse_body
from app.schemas.storage import ItemIn, ItemMove, ItemUpdate
from app.services import item_service
from app.utils.responses import ok, paged

bp = Blueprint("items", __name__, url_prefix="/api")


def _filters() -> dict:
    return {
        "q": request.args.get("q", ""),
        "room_id": int_arg("room_id"),
        "container_id": int_arg("container_id"),
        "include_descendants": bool_arg("include_descendants", True),
        "category_id": int_arg("category_id"),
        "tag_id": int_arg("tag_id"),
        "tag_name": request.args.get("tag_name", ""),
        "status": request.args.get("status", ""),
        "sort": request.args.get("sort", "updated_at"),
        "order": request.args.get("order", "desc"),
    }


@bp.get("/items")
def list_items():
    page = int_arg("page", 1) or 1
    page_size = int_arg("page_size", 20) or 20
    rows, total = item_service.list_items(_filters(), page=page, page_size=page_size)
    return paged(rows, total, page, page_size)


@bp.post("/items")
def create_item():
    body = parse_body(ItemIn)
    return ok(item_service.create_item(body.model_dump()), status=201)


@bp.get("/items/<int:item_id>")
def get_item(item_id: int):
    return ok(item_service.get_item(item_id).to_dict(detail=True))


@bp.put("/items/<int:item_id>")
def update_item(item_id: int):
    body = parse_body(ItemUpdate)
    return ok(item_service.update_item(item_id, body.model_dump(exclude_unset=True)))


@bp.post("/items/<int:item_id>/move")
def move_item(item_id: int):
    body = parse_body(ItemMove)
    return ok(
        item_service.move_item(
            item_id,
            room_id=body.room_id,
            room_name=body.room_name,
            container_id=body.container_id,
            container_path=body.container_path,
        )
    )


@bp.delete("/items/<int:item_id>")
def delete_item(item_id: int):
    item_service.delete_item(item_id)
    return ok({"deleted": True})
