"""标签 API。"""
from flask import Blueprint

from app.schemas.common import parse_body
from app.schemas.storage import TagIn, TagUpdate
from app.services import tag_service
from app.utils.responses import ok

bp = Blueprint("tags", __name__, url_prefix="/api")


@bp.get("/tags")
def list_tags():
    return ok(tag_service.list_tags())


@bp.post("/tags")
def create_tag():
    body = parse_body(TagIn)
    return ok(tag_service.create_tag(body.model_dump()), status=201)


@bp.put("/tags/<int:tag_id>")
def update_tag(tag_id: int):
    body = parse_body(TagUpdate)
    return ok(tag_service.update_tag(tag_id, body.model_dump(exclude_unset=True)))


@bp.delete("/tags/<int:tag_id>")
def delete_tag(tag_id: int):
    tag_service.delete_tag(tag_id)
    return ok({"deleted": True})
