"""物品大类服务。"""
from sqlalchemy import func

from app.extensions import db
from app.models import Category, Item
from app.services import log_service
from app.utils.errors import ApiError


def get_category(category_id: int) -> Category:
    category = db.session.get(Category, category_id)
    if not category:
        raise ApiError("分类不存在", 404)
    return category


def find_by_name(name: str) -> Category | None:
    return Category.query.filter_by(name=(name or "").strip()).first()


def list_categories() -> list[dict]:
    counts = dict(
        db.session.query(Item.category_id, func.count(Item.id))
        .filter(Item.category_id.isnot(None))
        .group_by(Item.category_id)
        .all()
    )
    rows = Category.query.order_by(Category.sort_order.asc(), Category.id.asc()).all()
    return [row.to_dict(item_count=counts.get(row.id, 0)) for row in rows]


def get_or_create(name: str, color: str | None = None) -> Category:
    name = (name or "").strip()
    if not name:
        raise ApiError("分类名称不能为空")
    category = find_by_name(name)
    if category:
        return category
    category = Category(name=name, color=color or "#5b8def")
    db.session.add(category)
    db.session.flush()
    return category


def create_category(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("分类名称不能为空")
    if find_by_name(name):
        raise ApiError(f"分类「{name}」已存在", 409)
    category = Category(
        name=name,
        description=data.get("description") or "",
        color=data.get("color") or "#5b8def",
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(category)
    db.session.flush()
    log_service.record("create", "category", category.id, {"name": name})
    db.session.commit()
    return category.to_dict(item_count=0)


def update_category(category_id: int, data: dict) -> dict:
    category = get_category(category_id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("分类名称不能为空")
        exists = Category.query.filter(Category.name == name, Category.id != category.id).first()
        if exists:
            raise ApiError(f"分类「{name}」已存在", 409)
        category.name = name
    if "description" in data:
        category.description = data.get("description") or ""
    if "color" in data:
        category.color = data.get("color") or category.color
    if "sort_order" in data:
        category.sort_order = int(data.get("sort_order") or 0)
    log_service.record("update", "category", category.id, data)
    db.session.commit()
    return category.to_dict()


def delete_category(category_id: int) -> None:
    category = get_category(category_id)
    for item in list(category.items):
        item.category_id = None
    log_service.record("delete", "category", category.id, {"name": category.name})
    db.session.delete(category)
    db.session.commit()
