from tests.conftest import create_container, create_room


def _create_item(client, auth, room_id, container_id=None, **extra):
    payload = {"name": "遥控器", "room_id": room_id, "container_id": container_id}
    payload.update(extra)
    response = client.post("/api/items", json=payload, headers=auth)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_room_crud_and_duplicate(client, auth):
    room = create_room(client, auth)
    assert room["name"] == "客厅"
    duplicate = client.post("/api/rooms", json={"name": "客厅"}, headers=auth)
    assert duplicate.status_code == 409

    listed = client.get("/api/rooms", headers=auth).get_json()["data"]
    assert len(listed) == 1

    updated = client.put(
        f"/api/rooms/{room['id']}", json={"description": "主客厅"}, headers=auth
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["description"] == "主客厅"

    deleted = client.delete(f"/api/rooms/{room['id']}", headers=auth)
    assert deleted.status_code == 200


def test_nested_containers_tree_and_path(client, auth):
    room = create_room(client, auth)
    tv = create_container(client, auth, room["id"], "电视柜")
    drawer = create_container(client, auth, room["id"], "上层抽屉", tv["id"])
    create_container(client, auth, room["id"], "下层抽屉", tv["id"])

    tree = client.get(
        f"/api/containers/tree?room_id={room['id']}", headers=auth
    ).get_json()["data"]["tree"]
    assert len(tree) == 1
    assert tree[0]["name"] == "电视柜"
    assert {node["name"] for node in tree[0]["children"]} == {"上层抽屉", "下层抽屉"}

    item = _create_item(client, auth, room["id"], drawer["id"])
    assert item["location_path"] == "客厅 / 电视柜 / 上层抽屉"


def test_item_color_family_is_optional(client, auth):
    room = create_room(client, auth)
    item = _create_item(client, auth, room["id"], color_family="黑色")
    assert item["color_family"] == "黑色"

    plain = _create_item(client, auth, room["id"], name="雨伞")
    assert plain["color_family"] == ""

    filtered = client.get("/api/items?color_family=黑色", headers=auth).get_json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == item["id"]

    updated = client.put(
        f"/api/items/{item['id']}", json={"color_family": " 蓝色 "}, headers=auth
    )
    assert updated.get_json()["data"]["color_family"] == "蓝色"

    cleared = client.put(
        f"/api/items/{item['id']}", json={"color_family": ""}, headers=auth
    )
    assert cleared.get_json()["data"]["color_family"] == ""

    by_keyword = client.get("/api/items?q=蓝色", headers=auth).get_json()["data"]
    assert by_keyword["total"] == 0


def test_item_crud_tags_and_search(client, auth):
    room = create_room(client, auth)
    item = _create_item(
        client,
        auth,
        room["id"],
        category_name="电子产品",
        tag_names=["常用", "充电"],
        description="65W 充电器",
    )
    assert item["category"]["name"] == "电子产品"
    assert {tag["name"] for tag in item["tags"]} == {"常用", "充电"}

    result = client.get("/api/items?q=充电", headers=auth).get_json()["data"]
    assert result["total"] == 1

    by_tag = client.get("/api/items?tag_name=常用", headers=auth).get_json()["data"]
    assert by_tag["total"] == 1

    updated = client.put(
        f"/api/items/{item['id']}", json={"quantity": 3}, headers=auth
    )
    assert updated.get_json()["data"]["quantity"] == 3

    cleared = client.put(
        f"/api/items/{item['id']}",
        json={"tag_names": [], "category_id": None},
        headers=auth,
    ).get_json()["data"]
    assert cleared["tags"] == []
    assert cleared["category"] is None

    client.delete(f"/api/items/{item['id']}", headers=auth)
    assert client.get(f"/api/items/{item['id']}", headers=auth).status_code == 404


def test_move_item_and_container_cross_room(client, auth):
    living = create_room(client, auth, "客厅")
    bedroom = create_room(client, auth, "卧室")
    cabinet = create_container(client, auth, living["id"], "电视柜")
    drawer = create_container(client, auth, living["id"], "抽屉", cabinet["id"])
    item = _create_item(client, auth, living["id"], drawer["id"])
    closet = create_container(client, auth, bedroom["id"], "衣柜")

    moved = client.post(
        f"/api/items/{item['id']}/move",
        json={"room_id": bedroom["id"], "container_id": closet["id"]},
        headers=auth,
    )
    assert moved.status_code == 200
    assert moved.get_json()["data"]["location_path"] == "卧室 / 衣柜"

    moved_container = client.post(
        f"/api/containers/{cabinet['id']}/move",
        json={"target_room_id": bedroom["id"]},
        headers=auth,
    )
    assert moved_container.status_code == 200

    tree = client.get(
        f"/api/containers/tree?room_id={bedroom['id']}", headers=auth
    ).get_json()["data"]["tree"]
    names = {node["name"] for node in tree}
    assert {"衣柜", "电视柜"} <= names


def test_delete_non_empty_room_is_blocked(client, auth):
    room = create_room(client, auth)
    create_container(client, auth, room["id"], "柜子")
    response = client.delete(f"/api/rooms/{room['id']}", headers=auth)
    assert response.status_code == 409


def test_category_and_tag_delete(client, auth):
    room = create_room(client, auth)
    category = client.post(
        "/api/categories", json={"name": "日用品"}, headers=auth
    ).get_json()["data"]
    tag = client.post("/api/tags", json={"name": "备用"}, headers=auth).get_json()["data"]
    item = _create_item(
        client,
        auth,
        room["id"],
        category_name="日用品",
        tag_names=["备用"],
    )

    assert client.delete(
        f"/api/categories/{category['id']}", headers=auth
    ).status_code == 200
    assert client.delete(f"/api/tags/{tag['id']}", headers=auth).status_code == 200

    detail = client.get(f"/api/items/{item['id']}", headers=auth).get_json()["data"]
    assert detail["category"] is None
    assert detail["tags"] == []


def test_container_path_resolution(client, auth):
    from app.services import container_service, room_service

    with client.application.app_context():
        room = room_service.create_room({"name": "书房"})
        top = container_service.create_container({"room_id": room["id"], "name": "书桌"})
        container_service.create_container(
            {"room_id": room["id"], "name": "抽屉", "parent_id": top["id"]}
        )
        resolved = container_service.resolve_container(room["id"], "书桌/抽屉")
        assert resolved is not None
        assert resolved.name == "抽屉"
        assert container_service.container_path(resolved) == "书房 / 书桌 / 抽屉"
