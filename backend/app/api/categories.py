"""分类 API。"""
from flask import Blueprint

from app.schemas.common import parse_body
from app.schemas.storage import CategoryIn, CategoryUpdate
from app.services import category_service
from app.utils.responses import ok

bp = Blueprint("categories", __name__, url_prefix="/api")


@bp.get("/categories")
def list_categories():
    return ok(category_service.list_categories())


@bp.post("/categories")
def create_category():
    body = parse_body(CategoryIn)
    return ok(category_service.create_category(body.model_dump()), status=201)


@bp.put("/categories/<int:category_id>")
def update_category(category_id: int):
    body = parse_body(CategoryUpdate)
    return ok(category_service.update_category(category_id, body.model_dump(exclude_unset=True)))


@bp.delete("/categories/<int:category_id>")
def delete_category(category_id: int):
    category_service.delete_category(category_id)
    return ok({"deleted": True})
