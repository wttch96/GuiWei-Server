"""物品相关工具：搜索、创建、更新、移动、打标签、删除。"""
from langchain_core.tools import tool

from app.services import item_service
from app.tools.common import container_ref, fail, find_item, guard, ok, room_ref, tag_list
from app.utils.errors import ApiError


@tool
def search_items(
    query: str = "",
    room: str = "",
    container_path: str = "",
    category: str = "",
    tag: str = "",
    status: str = "",
    color_family: str = "",
    limit: int = 20,
) -> str:
    """搜索物品。所有条件都可选，可组合使用。

    Args:
        query: 关键词，会匹配物品名称、描述、分类名、标签名和色系。
        room: 房间名称或 ID。
        container_path: 容器路径，例如 "电视柜/上层抽屉"；需同时提供 room。
        category: 分类名称。
        tag: 标签名称。
        status: 状态，可选 in_stock / lent / used_up / discarded。
        color_family: 色系，例如 黑色 / 白色 / 蓝色。
        limit: 返回条数，最多 50。
    """
    try:
        filters = {
            "q": query,
            "status": status,
            "tag_name": tag,
            "color_family": color_family,
            "page_size": max(1, min(50, int(limit or 20))),
        }
        if room:
            filters["room_id"] = room_ref(room).id
        if category:
            from app.services import category_service

            found = category_service.find_by_name(category)
            if not found:
                return ok({"total": 0, "items": [], "hint": f"分类「{category}」不存在"})
            filters["category_id"] = found.id
        if container_path:
            if not room:
                return fail("按容器搜索时必须同时提供 room（房间）")
            target_room = room_ref(room)
            container = container_ref(target_room, container_path)
            if not container:
                return fail(f"容器「{container_path}」不存在")
            filters["container_id"] = container.id
        rows, total = item_service.list_items(filters, page=1, page_size=filters["page_size"])
        return ok({"total": total, "items": rows})
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"搜索失败：{exc}", 500)


@tool
def get_item(item_id: int | None = None, name: str = "") -> str:
    """获取物品详情。用 ID 或名称指定；名称不唯一时会返回候选列表。

    Args:
        item_id: 物品 ID。
        name: 物品名称（支持部分匹配）。
    """
    try:
        item = find_item(item_id, name)
        return ok(item.to_dict(detail=True))
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"查询失败：{exc}", 500)


@tool
def create_item(
    name: str,
    room: str,
    container_path: str = "",
    category: str = "",
    tags: list[str] | str | None = None,
    description: str = "",
    quantity: int = 1,
    unit: str = "件",
    status: str = "in_stock",
    color_family: str = "",
) -> str:
    """创建物品并放到指定房间/容器。房间必须存在；容器不存在时会报错。

    Args:
        name: 物品名称。
        room: 房间名称或 ID。
        container_path: 容器路径，例如 "衣柜/顶层"；为空表示直接放在房间。
        category: 分类名称；不存在时会自动创建。
        tags: 标签名称列表，不存在时会自动创建。
        description: 物品描述。
        quantity: 数量，整数。
        unit: 单位，默认「件」。
        status: 状态，默认 in_stock。
        color_family: 色系（可选），例如 黑色 / 白色 / 蓝色；不确定就留空。
    """
    try:
        target_room = room_ref(room)
        container = container_ref(target_room, container_path)
        return guard(
            item_service.create_item,
            {
                "name": name,
                "room_id": target_room.id,
                "container_id": container.id if container else None,
                "category_name": category or None,
                "tag_names": tag_list(tags) or [],
                "description": description,
                "quantity": quantity,
                "unit": unit,
                "status": status,
                "color_family": color_family,
            },
        )
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"创建失败：{exc}", 500)


@tool
def update_item(
    item_id: int,
    name: str | None = None,
    description: str | None = None,
    quantity: int | None = None,
    unit: str | None = None,
    status: str | None = None,
    category: str | None = None,
    tags: list[str] | str | None = None,
    room: str | None = None,
    container_path: str | None = None,
    color_family: str | None = None,
) -> str:
    """更新物品字段。只传需要修改的字段。

    Args:
        item_id: 物品 ID。
        name: 新名称。
        description: 新描述。
        quantity: 新数量。
        unit: 新单位。
        status: 新状态：in_stock / lent / used_up / discarded。
        category: 新分类名称。
        tags: 新标签列表（会整体替换旧标签）。
        room: 新房间名称或 ID（移动位置时使用）。
        container_path: 新容器路径；传空字符串表示放到房间顶层。需要移动时优先用 move_item。
        color_family: 新色系（可选）；传空字符串表示清除。
    """
    data: dict = {}
    for key, value in {
        "name": name,
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "status": status,
        "color_family": color_family,
    }.items():
        if value is not None:
            data[key] = value
    if category is not None:
        data["category_name"] = category
    if tags is not None:
        data["tag_names"] = tag_list(tags) or []
    if room is not None or container_path is not None:
        try:
            target_room = room_ref(room) if room else None
            # 只给 container_path 时沿用物品当前房间
            if target_room:
                data["room_id"] = target_room.id
                if container_path is not None:
                    container = container_ref(target_room, container_path)
                    data["container_id"] = container.id if container else None
            elif container_path is not None:
                item = item_service.get_item(int(item_id))
                container = container_ref(item.room, container_path)
                data["container_id"] = container.id if container else None
        except ApiError as exc:
            return fail(exc.message, exc.status)
    return guard(item_service.update_item, int(item_id), data)


@tool
def move_item(item_id: int, room: str, container_path: str = "") -> str:
    """把物品移动到指定房间/容器。这是“把某物放到某处”的首选工具。

    Args:
        item_id: 物品 ID。
        room: 目标房间名称或 ID。
        container_path: 目标容器路径，例如 "电视柜/抽屉"；为空表示房间顶层。
    """
    try:
        target_room = room_ref(room)
        container = container_ref(target_room, container_path)
        return guard(
            item_service.move_item,
            int(item_id),
            target_room.id,
            None,
            container.id if container else None,
            None,
        )
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"移动失败：{exc}", 500)


@tool
def set_item_tags(item_id: int, tags: list[str] | str) -> str:
    """整体替换物品的标签。

    Args:
        item_id: 物品 ID。
        tags: 标签名称列表。
    """
    names = tag_list(tags) or []
    return guard(item_service.set_item_tags, int(item_id), [], names)


@tool
def delete_item(item_id: int, confirm: bool = False) -> str:
    """删除物品及其照片。危险操作，只有用户明确要求删除时才可调用。

    Args:
        item_id: 物品 ID。
        confirm: 必须显式传 true。
    """
    if not confirm:
        return ok({"deleted": False, "hint": "未执行删除：需要 confirm=true"})
    return guard(item_service.delete_item, int(item_id))


@tool
def list_item_photos(item_id: int) -> str:
    """列出某个物品的照片及识图结果。

    Args:
        item_id: 物品 ID。
    """
    try:
        item = item_service.get_item(int(item_id))
        return ok(
            {
                "item_id": item.id,
                "name": item.name,
                "photos": [photo.to_dict() for photo in item.photos],
            }
        )
    except ApiError as exc:
        return fail(exc.message, exc.status)
