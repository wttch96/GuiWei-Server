"""工具公共辅助：统一 JSON 返回、名称/ID 解析、精简序列化。"""
from typing import Any

from app.models import Item, Room
from app.services import container_service, room_service
from app.utils.errors import ApiError
from app.utils.serialize import dumps, iso


def ok(data: Any) -> str:
    return dumps({"ok": True, "data": data})


def fail(message: str, status: int = 400, **extra) -> str:
    return dumps({"ok": False, "error": message, "status": status, **extra})


def guard(fn, *args, **kwargs) -> str:
    """执行服务函数并把异常转换为模型可读的 JSON。"""
    try:
        return ok(fn(*args, **kwargs))
    except ApiError as exc:
        return fail(exc.message, exc.status, data=exc.data)
    except Exception as exc:  # 兜底，避免工具异常中断整个对话
        return fail(f"操作失败：{exc}", 500)


def room_ref(ref: str | int) -> Room:
    ref_text = str(ref or "").strip()
    if not ref_text:
        raise ApiError("需要提供房间名称或 ID")
    if ref_text.isdigit():
        return room_service.get_room(int(ref_text))
    room = room_service.find_room_by_name(ref_text)
    if not room:
        raise ApiError(f"房间「{ref_text}」不存在", 404)
    return room


def container_ref(room: Room, ref: str | int | None):
    ref_text = str(ref or "").strip()
    if not ref_text:
        return None
    if ref_text.isdigit():
        container = container_service.get_container(int(ref_text))
        if container.room_id != room.id:
            raise ApiError("该容器不属于指定房间", 400)
        return container
    clean = ref_text.replace(" / ", "/").replace("／", "/").strip("/")
    if clean == room.name:
        return None
    if clean.startswith(room.name + "/"):
        clean = clean[len(room.name) + 1 :]
    return container_service.resolve_container(room.id, clean)


def tag_list(tags: list[str] | str | None) -> list[str] | None:
    if tags is None:
        return None
    if isinstance(tags, str):
        return [part.strip() for part in tags.replace("，", ",").split(",") if part.strip()]
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def item_brief(item: Item) -> dict:
    primary = item.primary_photo()
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description[:300],
        "category": item.category.name if item.category else None,
        "tags": [tag.name for tag in item.tags],
        "quantity": item.quantity,
        "unit": item.unit,
        "status": item.status,
        "location": item.location_path(),
        "photo_id": primary.id if primary else None,
        "updated_at": iso(item.updated_at),
    }


def find_item(item_id: int | None = None, name: str | None = None) -> Item:
    from app.extensions import db
    from app.services import item_service

    if item_id:
        return item_service.get_item(int(item_id))
    name = (name or "").strip()
    if not name:
        raise ApiError("需要提供物品 ID 或名称")
    matches = item_service.find_items_by_name(name)
    if not matches:
        raise ApiError(f"没有找到名称包含「{name}」的物品", 404)
    if len(matches) > 1:
        raise ApiError(
            f"找到多件匹配「{name}」的物品，请用 ID 指定其中一件："
            + "；".join(
                f"#{item.id} {item.name}（{item.location_path()}）" for item in matches[:5]
            ),
            409,
        )
    return db.session.merge(matches[0])
