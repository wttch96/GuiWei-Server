"""全局搜索：房间 / 容器 / 物品 / 分类 / 标签。"""
from app.models import Category, Container, Room, Tag
from app.services import container_service, item_service
from app.services import room_service


def search(q: str, limit: int = 8) -> dict:
    term = (q or "").strip()
    if not term:
        return {"rooms": [], "containers": [], "items": [], "categories": [], "tags": []}
    like = f"%{term}%"

    rooms = Room.query.filter(Room.name.ilike(like)).limit(limit).all()
    containers = (
        Container.query.filter(Container.name.ilike(like))
        .order_by(Container.id.asc())
        .limit(limit)
        .all()
    )
    items, _ = item_service.list_items({"q": term, "page_size": limit}, page=1, page_size=limit)
    categories = Category.query.filter(Category.name.ilike(like)).limit(limit).all()
    tags = Tag.query.filter(Tag.name.ilike(like)).limit(limit).all()

    return {
        "rooms": [room.to_dict() for room in rooms],
        "containers": [
            {**row.to_dict(), "path": container_service.container_path(row)}
            for row in containers
        ],
        "items": items,
        "categories": [row.to_dict() for row in categories],
        "tags": [row.to_dict() for row in tags],
    }
