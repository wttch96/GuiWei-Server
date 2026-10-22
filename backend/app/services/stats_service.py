"""统计概览。"""
from sqlalchemy import func

from app.extensions import db
from app.models import Category, Container, Item, Photo, Room, Tag, item_tags


def overview() -> dict:
    items_by_room_rows = (
        db.session.query(Room.id, Room.name, Room.color, func.count(Item.id))
        .outerjoin(Item, Item.room_id == Room.id)
        .group_by(Room.id)
        .order_by(Room.sort_order.asc(), Room.id.asc())
        .all()
    )
    items_by_category_rows = (
        db.session.query(Category.id, Category.name, Category.color, func.count(Item.id))
        .outerjoin(Item, Item.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order.asc(), Category.id.asc())
        .all()
    )
    uncategorized = Item.query.filter(Item.category_id.is_(None)).count()
    status_rows = (
        db.session.query(Item.status, func.count(Item.id)).group_by(Item.status).all()
    )
    tag_rows = (
        db.session.query(Tag.id, Tag.name, Tag.color, func.count(item_tags.c.item_id))
        .outerjoin(item_tags, item_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(item_tags.c.item_id).desc())
        .limit(8)
        .all()
    )
    recent = Item.query.order_by(Item.updated_at.desc(), Item.id.desc()).limit(8).all()

    return {
        "counts": {
            "rooms": Room.query.count(),
            "containers": Container.query.count(),
            "items": Item.query.count(),
            "categories": Category.query.count(),
            "tags": Tag.query.count(),
            "photos": Photo.query.count(),
        },
        "quantity_total": int(
            db.session.query(func.coalesce(func.sum(Item.quantity), 0)).scalar() or 0
        ),
        "items_by_room": [
            {"id": rid, "name": name, "color": color, "count": count}
            for rid, name, color, count in items_by_room_rows
        ],
        "items_by_category": [
            {"id": cid, "name": name, "color": color, "count": count}
            for cid, name, color, count in items_by_category_rows
        ]
        + (
            [{"id": None, "name": "未分类", "color": "#c0c4cc", "count": uncategorized}]
            if uncategorized
            else []
        ),
        "items_by_status": [{"status": status, "count": count} for status, count in status_rows],
        "top_tags": [
            {"id": tid, "name": name, "color": color, "count": count}
            for tid, name, color, count in tag_rows
        ],
        "recent_items": [item.to_dict() for item in recent],
    }
