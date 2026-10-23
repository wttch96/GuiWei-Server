"""容器服务：支持无限层级，提供树、路径解析、跨房间移动。"""
import re

from sqlalchemy import func

from app.extensions import db
from app.models import Container, Item, Room
from app.services import log_service
from app.utils.errors import ApiError

_SUFFIX_RE = re.compile(r"[（(][^（()）]*[）)]$")


def _match_container(room_id: int, parent_id: int | None, part: str) -> Container | None:
    """按名称、昵称或「柜子A（药柜）」式的展示名匹配同级容器。"""
    query = Container.query.filter_by(room_id=room_id, parent_id=parent_id).order_by(
        Container.sort_order.asc(), Container.id.asc()
    )
    node = query.filter(Container.name == part).first()
    if node:
        return node
    node = query.filter(Container.nickname == part).first()
    if node:
        return node
    stripped = _SUFFIX_RE.sub("", part).strip()
    if stripped and stripped != part:
        return query.filter(Container.name == stripped).first()
    return None


def get_container(container_id: int) -> Container:
    container = db.session.get(Container, container_id)
    if not container:
        raise ApiError("容器不存在", 404)
    return container


def item_count_map() -> dict[int, int]:
    return dict(
        db.session.query(Item.container_id, func.count(Item.id))
        .filter(Item.container_id.isnot(None))
        .group_by(Item.container_id)
        .all()
    )


def list_containers(room_id: int) -> list[dict]:
    room = db.session.get(Room, room_id)
    if not room:
        raise ApiError("房间不存在", 404)
    counts = item_count_map()
    rows = (
        Container.query.filter_by(room_id=room_id)
        .order_by(Container.sort_order.asc(), Container.id.asc())
        .all()
    )
    return [row.to_dict(item_count=counts.get(row.id, 0)) for row in rows]


def list_tree(room_id: int) -> list[dict]:
    counts = item_count_map()
    rows = (
        Container.query.filter_by(room_id=room_id)
        .order_by(Container.sort_order.asc(), Container.id.asc())
        .all()
    )
    nodes = {row.id: {**row.to_dict(item_count=counts.get(row.id, 0)), "children": []} for row in rows}
    roots: list[dict] = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id and row.parent_id in nodes:
            nodes[row.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def container_path(container: Container, include_room: bool = True) -> str:
    parts = container.path_names()
    if include_room and container.room:
        parts = [container.room.name] + parts
    return " / ".join(parts)


def resolve_container(room_id: int, path: str | None = None, container_id: int | None = None) -> Container | None:
    """按 ID、名称或「柜子/抽屉」式路径解析容器。"""
    if container_id:
        container = get_container(container_id)
        if container.room_id != room_id:
            raise ApiError("容器不属于指定房间", 400)
        return container
    path = (path or "").strip().strip("/")
    if not path:
        return None
    parts = [p.strip() for p in path.replace("\\", "/").split("/") if p.strip()]
    if len(parts) > 1:
        parent = None
        for part in parts:
            node = _match_container(room_id, parent.id if parent else None, part)
            if not node:
                raise ApiError(f"容器路径「{path}」不存在", 404)
            parent = node
        return parent
    node = _match_container(room_id, None, parts[0])
    if not node:
        raise ApiError(f"容器「{path}」不存在", 404)
    return node


def _check_sibling_name(room_id: int, parent_id: int | None, name: str, exclude_id: int | None = None):
    query = Container.query.filter_by(room_id=room_id, parent_id=parent_id, name=name)
    if exclude_id:
        query = query.filter(Container.id != exclude_id)
    if query.first():
        raise ApiError(f"同一层级下已存在容器「{name}」", 409)


def create_container(data: dict) -> dict:
    room_id = int(data.get("room_id") or 0)
    room = db.session.get(Room, room_id)
    if not room:
        raise ApiError("房间不存在", 404)
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("容器名称不能为空")
    parent_id = data.get("parent_id")
    parent = None
    if parent_id:
        parent = get_container(int(parent_id))
        if parent.room_id != room_id:
            raise ApiError("父容器不属于该房间", 400)
    _check_sibling_name(room_id, parent.id if parent else None, name)
    container = Container(
        room_id=room_id,
        parent_id=parent.id if parent else None,
        name=name,
        nickname=(data.get("nickname") or "").strip(),
        code=data.get("code") or "",
        description=data.get("description") or "",
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(container)
    db.session.flush()
    log_service.record(
        "create", "container", container.id, {"name": name, "path": container_path(container)}
    )
    db.session.commit()
    return container.to_dict(item_count=0)


def update_container(container_id: int, data: dict) -> dict:
    container = get_container(container_id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("容器名称不能为空")
        _check_sibling_name(container.room_id, container.parent_id, name, exclude_id=container.id)
        container.name = name
    if "nickname" in data:
        container.nickname = (data.get("nickname") or "").strip()
    if "code" in data:
        container.code = data.get("code") or ""
    if "description" in data:
        container.description = data.get("description") or ""
    if "sort_order" in data:
        container.sort_order = int(data.get("sort_order") or 0)
    log_service.record("update", "container", container.id, data)
    db.session.commit()
    return container.to_dict()


def _descendant_ids(container: Container) -> list[int]:
    result: list[int] = []
    stack = list(container.children)
    while stack:
        node = stack.pop()
        result.append(node.id)
        stack.extend(node.children)
    return result


def _is_descendant(candidate: Container, ancestor: Container) -> bool:
    node = candidate
    seen: set[int] = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        if node.id == ancestor.id:
            return True
        node = node.parent
    return False


def move_container(container_id: int, target_room_id: int, target_parent_id: int | None = None) -> dict:
    container = get_container(container_id)
    target_room = db.session.get(Room, target_room_id)
    if not target_room:
        raise ApiError("目标房间不存在", 404)
    parent = None
    if target_parent_id:
        parent = get_container(int(target_parent_id))
        if parent.room_id != target_room.id:
            raise ApiError("目标父容器不属于目标房间", 400)
        if _is_descendant(parent, container):
            raise ApiError("不能把容器移动到它自己或它的子容器中", 400)
    if parent and parent.id == container.id:
        raise ApiError("不能把容器移动到自身", 400)
    _check_sibling_name(target_room.id, parent.id if parent else None, container.name, exclude_id=container.id)

    # 整棵子树和其中的物品一起迁移房间
    moved_ids = [container.id] + _descendant_ids(container)
    Container.query.filter(Container.id.in_(moved_ids)).update(
        {Container.room_id: target_room.id}, synchronize_session=False
    )
    Item.query.filter(Item.container_id.in_(moved_ids)).update(
        {Item.room_id: target_room.id}, synchronize_session=False
    )
    container.parent_id = parent.id if parent else None
    log_service.record(
        "move",
        "container",
        container.id,
        {"target_room": target_room.name, "target_parent_id": parent.id if parent else None},
    )
    db.session.commit()
    db.session.refresh(container)
    return container.to_dict()


def delete_container(container_id: int) -> None:
    container = get_container(container_id)
    child_count = Container.query.filter_by(parent_id=container.id).count()
    item_count = Item.query.filter_by(container_id=container.id).count()
    if child_count or item_count:
        raise ApiError(
            f"容器内还有 {child_count} 个子容器、{item_count} 件物品，请先清空后再删除",
            409,
        )
    log_service.record("delete", "container", container.id, {"path": container_path(container)})
    db.session.delete(container)
    db.session.commit()


def subtree_ids(container_id: int) -> list[int]:
    container = get_container(container_id)
    return [container.id] + _descendant_ids(container)


def subtree_ids_map(room_id: int) -> dict[int, list[int]]:
    """一次性计算房间内每个容器的子树 ID，避免 N+1。"""
    rows = Container.query.filter_by(room_id=room_id).all()
    children: dict[int | None, list[Container]] = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)
    result: dict[int, list[int]] = {}

    def walk(node: Container) -> list[int]:
        ids = [node.id]
        for child in children.get(node.id, []):
            ids.extend(walk(child))
        result[node.id] = ids
        return ids

    for row in children.get(None, []):
        walk(row)
    return result
