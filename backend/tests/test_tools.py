import json

from app.tools import get_tool_map, get_tools


def _invoke(tool_name, **kwargs):
    return json.loads(get_tool_map()[tool_name].invoke(kwargs))


def test_tool_registry_is_complete():
    names = {tool.name for tool in get_tools()}
    expected = {
        "list_rooms",
        "create_room",
        "update_room",
        "delete_room",
        "list_containers",
        "create_container",
        "update_container",
        "move_container",
        "delete_container",
        "search_items",
        "get_item",
        "create_item",
        "update_item",
        "move_item",
        "set_item_tags",
        "delete_item",
        "list_categories",
        "create_category",
        "update_category",
        "delete_category",
        "list_tags",
        "create_tag",
        "update_tag",
        "delete_tag",
        "recognize_photo",
        "inventory_overview",
        "global_search",
    }
    assert expected <= names
    assert len(names) == len(get_tools())


def test_tools_full_storage_flow(app):
    with app.app_context():
        room = _invoke("create_room", name="客厅")
        assert room["ok"] is True
        room_id = room["data"]["id"]

        cabinet = _invoke("create_container", room="客厅", name="电视柜")
        assert cabinet["ok"] is True
        drawer = _invoke(
            "create_container", room=str(room_id), name="抽屉", parent_path="电视柜"
        )
        assert drawer["ok"] is True

        item = _invoke(
            "create_item",
            name="遥控器",
            room="客厅",
            container_path="电视柜/抽屉",
            category="电子产品",
            tags=["常用"],
            description="黑色遥控器",
        )
        assert item["ok"] is True, item
        item_id = item["data"]["id"]
        assert item["data"]["location_path"] == "客厅 / 电视柜 / 抽屉"

        found = _invoke("search_items", query="遥控")
        assert found["ok"] is True
        assert found["data"]["total"] == 1

        detail = _invoke("get_item", item_id=item_id)
        assert detail["data"]["category"]["name"] == "电子产品"

        moved = _invoke("move_item", item_id=item_id, room="客厅", container_path="")
        assert moved["ok"] is True
        assert moved["data"]["location_path"] == "客厅"

        listed = _invoke("list_containers", room="客厅")
        assert listed["ok"] is True
        assert listed["data"][0]["containers"]

        # 未确认时不会删除
        refused = _invoke("delete_item", item_id=item_id)
        assert refused["data"]["deleted"] is False
        deleted = _invoke("delete_item", item_id=item_id, confirm=True)
        assert deleted["ok"] is True

        overview = _invoke("inventory_overview")
        assert overview["ok"] is True
        assert overview["data"]["counts"]["items"] == 0


def test_tool_error_is_json_not_exception(app):
    with app.app_context():
        result = _invoke("get_item", item_id=9999)
        assert result["ok"] is False
        assert result["status"] == 404


def test_tool_ambigious_item_name(app):
    with app.app_context():
        _invoke("create_room", name="客厅")
        _invoke("create_item", name="充电器", room="客厅", quantity=1)
        _invoke("create_item", name="充电器", room="客厅", quantity=2)
        result = _invoke("get_item", name="充电器")
        assert result["ok"] is False
        assert result["status"] == 409
