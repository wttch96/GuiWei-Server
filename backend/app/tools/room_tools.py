"""房间相关工具。"""
from langchain_core.tools import tool

from app.services import room_service
from app.tools.common import guard, ok


@tool
def list_rooms() -> str:
    """列出所有房间，包含每个房间的容器数和物品数。需要知道有哪些房间时先调用它。"""
    return guard(room_service.list_rooms)


@tool
def create_room(name: str, description: str = "", color: str = "#2f7d6d") -> str:
    """创建一个房间。

    Args:
        name: 房间名称，例如「客厅」「书房」「儿童房」，必须唯一。
        description: 房间描述，可为空。
        color: 十六进制颜色，例如 #2f7d6d。
    """
    return guard(room_service.create_room, {"name": name, "description": description, "color": color})


@tool
def update_room(
    room_id: int,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
    sort_order: int | None = None,
) -> str:
    """修改房间信息。只传需要修改的字段。

    Args:
        room_id: 房间 ID，可先用 list_rooms 获取。
        name: 新名称。
        description: 新描述。
        color: 新颜色。
        sort_order: 排序值，越小越靠前。
    """
    data = {}
    for key, value in {
        "name": name,
        "description": description,
        "color": color,
        "sort_order": sort_order,
    }.items():
        if value is not None:
            data[key] = value
    return guard(room_service.update_room, int(room_id), data)


@tool
def delete_room(room_id: int, confirm: bool = False) -> str:
    """删除房间。危险操作，只有用户明确要求删除时才可调用。

    Args:
        room_id: 要删除的房间 ID。
        confirm: 必须显式传 true，否则不会执行。
    """
    if not confirm:
        return ok({"deleted": False, "hint": "未执行删除：需要 confirm=true"})
    return guard(room_service.delete_room, int(room_id))
