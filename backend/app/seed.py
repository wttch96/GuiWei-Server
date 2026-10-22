"""演示数据。仅用于本地体验：flask --app run.py seed-demo"""
from app.models import Container, Room
from app.services import (
    category_service,
    container_service,
    item_service,
    room_service,
    tag_service,
)
from app.utils.errors import ApiError


def _room(name: str) -> dict:
    return room_service.create_room({"name": name})


def _container(room_id: int, name: str, parent_id: int | None = None) -> dict:
    return container_service.create_container(
        {"room_id": room_id, "name": name, "parent_id": parent_id}
    )


def seed_demo() -> dict:
    if Room.query.count() > 0:
        raise ApiError("数据库中已有房间数据，演示数据不会覆盖", 409)

    living = _room("客厅")
    bedroom = _room("卧室")
    study = _room("书房")

    tv = _container(living["id"], "电视柜")
    tv_top = _container(living["id"], "上层抽屉", tv["id"])
    tv_bottom = _container(living["id"], "下层抽屉", tv["id"])
    box = _container(living["id"], "收纳箱 A")

    wardrobe = _container(bedroom["id"], "衣柜")
    wardrobe_top = _container(bedroom["id"], "顶部收纳盒", wardrobe["id"])

    desk = _container(study["id"], "书桌")
    desk_drawer = _container(study["id"], "第一层抽屉", desk["id"])
    cabinet = _container(study["id"], "文件柜")

    categories = {}
    for name, color in [
        ("电子产品", "#5b8def"),
        ("日用品", "#2f7d6d"),
        ("衣物", "#e6a23c"),
        ("证件", "#9b59b6"),
        ("药品", "#f56c6c"),
    ]:
        categories[name] = category_service.create_category({"name": name, "color": color})["id"]

    tags = {}
    for name, color in [
        ("常用", "#2f7d6d"),
        ("备用", "#909399"),
        ("充电", "#5b8def"),
        ("冬季", "#e6a23c"),
        ("重要", "#f56c6c"),
    ]:
        tags[name] = tag_service.create_tag({"name": name, "color": color})["id"]

    items = [
        ("电视遥控器", living["id"], tv_top["id"], "电子产品", ["常用"], "黑色的电视遥控器"),
        ("HDMI 线", living["id"], tv_bottom["id"], "电子产品", ["备用"], "2 米 HDMI 2.1 线"),
        ("USD-C 充电器", study["id"], desk_drawer["id"], "电子产品", ["常用", "充电"], "65W 氮化镓充电器"),
        ("羽绒服", bedroom["id"], wardrobe_top["id"], "衣物", ["冬季"], "黑色长款羽绒服"),
        ("护照", study["id"], cabinet["id"], "证件", ["重要"], "中国护照"),
        ("创可贴", living["id"], box["id"], "药品", ["常用"], "防水创可贴一盒"),
    ]
    for name, room_id, container_id, category_name, tag_names, description in items:
        item_service.create_item(
            {
                "name": name,
                "room_id": room_id,
                "container_id": container_id,
                "category_id": categories[category_name],
                "tag_ids": [tags[tag] for tag in tag_names],
                "description": description,
                "quantity": 1,
            }
        )

    return {
        "rooms": 3,
        "containers": 9,
        "items": len(items),
        "categories": len(categories),
        "tags": len(tags),
        "container_ids": [tv["id"], tv_top["id"]],
        "note": "演示数据已创建",
    }
