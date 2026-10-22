"""容器相关工具。"""
from langchain_core.tools import tool

from app.services import container_service, room_service
from app.tools.common import container_ref, guard, ok, room_ref
from app.utils.serialize import dumps


def _room_summary(room) -> dict:
    tree = container_service.list_tree(room.id)
    flat = container_service.list_containers(room.id)
    for row in flat:
        node = container_service.get_container(row["id"])
        row["path"] = container_service.container_path(node)
    return {
        "room_id": room.id,
        "room_name": room.name,
        "tree": tree,
        "containers": flat,
    }


@tool
def list_containers(room: str | None = None) -> str:
    """列出容器。可指定房间名称或 ID；不指定时列出所有房间的容器。

    Args:
        room: 房间名称或 ID，例如「客厅」或 "1"。
    """
    try:
        if room:
            target = room_ref(room)
            return dumps({"ok": True, "data": [_room_summary(target)]})
        data = []
        for item in room_service.list_rooms():
            target = room_service.get_room(item["id"])
            data.append(_room_summary(target))
        return dumps({"ok": True, "data": data})
    except Exception as exc:
        return dumps({"ok": False, "error": str(exc)})


@tool
def create_container(
    room: str,
    name: str,
    parent_path: str = "",
    description: str = "",
    code: str = "",
) -> str:
    """在房间中创建容器，容器可以多级嵌套。

    Args:
        room: 房间名称或 ID。
        name: 容器名称，例如「电视柜」「抽屉」「收纳盒 A」。
        parent_path: 父容器路径，例如 "电视柜" 或 "电视柜/上层抽屉"；为空表示房间顶层。
        description: 容器描述。
        code: 自定义编号/位置码，可为空。
    """
    try:
        target_room = room_ref(room)
        parent = container_ref(target_room, parent_path)
        return guard(
            container_service.create_container,
            {
                "room_id": target_room.id,
                "name": name,
                "parent_id": parent.id if parent else None,
                "description": description,
                "code": code,
            },
        )
    except Exception as exc:
        return dumps({"ok": False, "error": str(exc)})


@tool
def update_container(
    container_id: int,
    name: str | None = None,
    description: str | None = None,
    code: str | None = None,
    sort_order: int | None = None,
) -> str:
    """修改容器信息。只传需要修改的字段。

    Args:
        container_id: 容器 ID。
        name: 新名称。
        description: 新描述。
        code: 新编号。
        sort_order: 排序值。
    """
    data = {}
    for key, value in {
        "name": name,
        "description": description,
        "code": code,
        "sort_order": sort_order,
    }.items():
        if value is not None:
            data[key] = value
    return guard(container_service.update_container, int(container_id), data)


@tool
def move_container(
    container_id: int,
    target_room: str,
    target_parent_path: str = "",
) -> str:
    """把容器（连同子容器和物品）移动到另一个房间或父容器下。

    Args:
        container_id: 要移动的容器 ID。
        target_room: 目标房间名称或 ID。
        target_parent_path: 目标父容器路径；为空表示放到目标房间顶层。
    """
    try:
        room = room_ref(target_room)
        parent = container_ref(room, target_parent_path)
        return guard(
            container_service.move_container,
            int(container_id),
            room.id,
            parent.id if parent else None,
        )
    except Exception as exc:
        return dumps({"ok": False, "error": str(exc)})


@tool
def delete_container(container_id: int, confirm: bool = False) -> str:
    """删除空容器。危险操作，只有用户明确要求删除时才可调用。

    Args:
        container_id: 容器 ID。
        confirm: 必须显式传 true。
    """
    if not confirm:
        return ok({"deleted": False, "hint": "未执行删除：需要 confirm=true"})
    return guard(container_service.delete_container, int(container_id))
