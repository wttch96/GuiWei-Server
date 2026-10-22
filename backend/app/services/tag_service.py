"""标签服务。"""
from sqlalchemy import func

from app.extensions import db
from app.models import Tag, item_tags
from app.services import log_service
from app.utils.errors import ApiError


def get_tag(tag_id: int) -> Tag:
    tag = db.session.get(Tag, tag_id)
    if not tag:
        raise ApiError("标签不存在", 404)
    return tag


def find_by_name(name: str) -> Tag | None:
    return Tag.query.filter_by(name=(name or "").strip()).first()


def list_tags() -> list[dict]:
    counts = dict(
        db.session.query(item_tags.c.tag_id, func.count(item_tags.c.item_id))
        .group_by(item_tags.c.tag_id)
        .all()
    )
    rows = Tag.query.order_by(Tag.id.asc()).all()
    return [row.to_dict(item_count=counts.get(row.id, 0)) for row in rows]


def get_or_create(name: str, color: str | None = None) -> Tag:
    name = (name or "").strip()
    if not name:
        raise ApiError("标签名称不能为空")
    tag = find_by_name(name)
    if tag:
        return tag
    tag = Tag(name=name, color=color or "#8b8b8b")
    db.session.add(tag)
    db.session.flush()
    return tag


def resolve_tags(tag_ids: list[int] | None = None, tag_names: list[str] | None = None) -> list[Tag]:
    result: list[Tag] = []
    seen: set[int] = set()
    for tag_id in tag_ids or []:
        tag = get_tag(int(tag_id))
        if tag.id not in seen:
            seen.add(tag.id)
            result.append(tag)
    for name in tag_names or []:
        if not (name or "").strip():
            continue
        tag = get_or_create(name)
        if tag.id not in seen:
            seen.add(tag.id)
            result.append(tag)
    return result


def create_tag(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("标签名称不能为空")
    if find_by_name(name):
        raise ApiError(f"标签「{name}」已存在", 409)
    tag = Tag(name=name, color=data.get("color") or "#8b8b8b")
    db.session.add(tag)
    db.session.flush()
    log_service.record("create", "tag", tag.id, {"name": name})
    db.session.commit()
    return tag.to_dict(item_count=0)


def update_tag(tag_id: int, data: dict) -> dict:
    tag = get_tag(tag_id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("标签名称不能为空")
        exists = Tag.query.filter(Tag.name == name, Tag.id != tag.id).first()
        if exists:
            raise ApiError(f"标签「{name}」已存在", 409)
        tag.name = name
    if "color" in data:
        tag.color = data.get("color") or tag.color
    log_service.record("update", "tag", tag.id, data)
    db.session.commit()
    return tag.to_dict()


def delete_tag(tag_id: int) -> None:
    tag = get_tag(tag_id)
    # 通过 ORM 解除关联，避免与已加载的 tag.items 集合产生重复删除
    for item in list(tag.items):
        item.tags.remove(tag)
    log_service.record("delete", "tag", tag.id, {"name": tag.name})
    db.session.delete(tag)
    db.session.commit()
