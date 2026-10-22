"""LangChain 工具注册表。

所有对数据的读写都经由这里暴露给 AI；API 层直接调用 services，
两层共用同一套业务逻辑，行为保持一致。
"""
from app.tools.category_tools import (
    create_category,
    delete_category,
    list_categories,
    update_category,
)
from app.tools.container_tools import (
    create_container,
    delete_container,
    list_containers,
    move_container,
    update_container,
)
from app.tools.item_tools import (
    create_item,
    delete_item,
    get_item,
    list_item_photos,
    move_item,
    search_items,
    set_item_tags,
    update_item,
)
from app.tools.photo_tools import recognize_photo
from app.tools.room_tools import create_room, delete_room, list_rooms, update_room
from app.tools.stats_tools import global_search, inventory_overview
from app.tools.tag_tools import create_tag, delete_tag, list_tags, update_tag

ALL_TOOLS = [
    # 房间
    list_rooms,
    create_room,
    update_room,
    delete_room,
    # 容器
    list_containers,
    create_container,
    update_container,
    move_container,
    delete_container,
    # 物品
    search_items,
    get_item,
    create_item,
    update_item,
    move_item,
    set_item_tags,
    delete_item,
    list_item_photos,
    # 分类 / 标签
    list_categories,
    create_category,
    update_category,
    delete_category,
    list_tags,
    create_tag,
    update_tag,
    delete_tag,
    # 照片 / 统计 / 搜索
    recognize_photo,
    inventory_overview,
    global_search,
]


def get_tools() -> list:
    return list(ALL_TOOLS)


def get_tool_map() -> dict:
    return {tool.name: tool for tool in ALL_TOOLS}
