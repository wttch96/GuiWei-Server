import json

from tests.conftest import create_room


def _upload(client, auth, png_bytes):
    response = client.post(
        "/api/photos",
        data={"file": (__import__("io").BytesIO(png_bytes), "test.png")},
        content_type="multipart/form-data",
        headers=auth,
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_upload_and_download_photo(client, auth, png_bytes, token):
    photo = _upload(client, auth, png_bytes)
    assert photo["width"] == 32 and photo["height"] == 24
    assert photo["mime_type"] == "image/png"

    unauthorized = client.get(f"/api/photos/{photo['id']}/file")
    assert unauthorized.status_code == 401

    response = client.get(f"/api/photos/{photo['id']}/file?token={token}")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert len(response.data) > 0


def test_reject_non_image(client, auth):
    import io

    response = client.post(
        "/api/photos",
        data={"file": (io.BytesIO(b"not an image"), "bad.txt")},
        content_type="multipart/form-data",
        headers=auth,
    )
    assert response.status_code == 400


def test_attach_photo_to_item_and_primary(client, auth, png_bytes):
    room = create_room(client, auth)
    item = client.post(
        "/api/items", json={"name": "耳机", "room_id": room["id"]}, headers=auth
    ).get_json()["data"]
    photo = _upload(client, auth, png_bytes)

    attached = client.post(
        f"/api/photos/{photo['id']}/attach", json={"item_id": item["id"]}, headers=auth
    )
    assert attached.status_code == 200
    assert attached.get_json()["data"]["is_primary"] is True

    detail = client.get(f"/api/items/{item['id']}", headers=auth).get_json()["data"]
    assert detail["photo_count"] == 1
    assert detail["primary_photo"]["id"] == photo["id"]


def test_switch_primary_photo(client, auth, png_bytes):
    room = create_room(client, auth)
    item = client.post(
        "/api/items", json={"name": "移动硬盘", "room_id": room["id"]}, headers=auth
    ).get_json()["data"]

    first = _upload(client, auth, png_bytes)
    second = _upload(client, auth, png_bytes)
    for photo in (first, second):
        response = client.post(
            f"/api/photos/{photo['id']}/attach",
            json={"item_id": item["id"]},
            headers=auth,
        )
        assert response.status_code == 200

    # 第二张不是主图；把第一张重新设为主图也必须返回 True
    response = client.post(f"/api/photos/{first['id']}/primary", headers=auth)
    assert response.status_code == 200
    assert response.get_json()["data"]["is_primary"] is True

    detail = client.get(f"/api/items/{item['id']}", headers=auth).get_json()["data"]
    assert detail["primary_photo"]["id"] == first["id"]

    response = client.post(f"/api/photos/{second['id']}/primary", headers=auth)
    assert response.get_json()["data"]["is_primary"] is True
    detail = client.get(f"/api/items/{item['id']}", headers=auth).get_json()["data"]
    assert detail["primary_photo"]["id"] == second["id"]


def test_attach_primary_photo_to_another_item(client, auth, png_bytes):
    room = create_room(client, auth)
    first_item = client.post(
        "/api/items", json={"name": "相机", "room_id": room["id"]}, headers=auth
    ).get_json()["data"]
    second_item = client.post(
        "/api/items", json={"name": "镜头", "room_id": room["id"]}, headers=auth
    ).get_json()["data"]

    first = _upload(client, auth, png_bytes)
    backup = _upload(client, auth, png_bytes)
    target = _upload(client, auth, png_bytes)
    for photo, item_id in ((first, first_item["id"]), (backup, first_item["id"]), (target, second_item["id"])):
        client.post(
            f"/api/photos/{photo['id']}/attach",
            json={"item_id": item_id},
            headers=auth,
        )

    # 把原物品的主图转移到已有主图的物品：两边都应保留唯一主图
    client.post(f"/api/photos/{first['id']}/attach", json={"item_id": second_item["id"]}, headers=auth)

    first_detail = client.get(f"/api/items/{first_item['id']}", headers=auth).get_json()["data"]
    second_detail = client.get(f"/api/items/{second_item['id']}", headers=auth).get_json()["data"]
    assert first_detail["primary_photo"]["id"] == backup["id"]
    assert second_detail["primary_photo"]["id"] == target["id"]
    assert first_detail["photo_count"] == 1
    assert second_detail["photo_count"] == 2


def test_analyze_photo_creates_item(client, auth, png_bytes, monkeypatch):
    from app.services import vision_service

    room = create_room(client, auth)
    photo = _upload(client, auth, png_bytes)

    suggestion = {
        "name": "蓝牙耳机",
        "description": "白色入耳式蓝牙耳机",
        "category": "电子产品",
        "tags": ["常用", "充电"],
        "quantity": 1,
        "location_hint": "书房/抽屉",
        "confidence": 0.9,
        "raw_text": "",
        "raw_content": "{}",
    }

    def fake_analyze(photo_obj):
        photo_obj.ai_text = json.dumps(suggestion, ensure_ascii=False)
        photo_obj.ai_result = json.dumps(suggestion, ensure_ascii=False)
        return suggestion

    monkeypatch.setattr(vision_service, "analyze_photo", fake_analyze)

    result = client.post(
        f"/api/photos/{photo['id']}/analyze",
        json={"create_item": True, "room_id": room["id"]},
        headers=auth,
    )
    assert result.status_code == 200, result.get_json()
    data = result.get_json()["data"]
    assert data["item"]["name"] == "蓝牙耳机"
    assert data["item"]["category"]["name"] == "电子产品"
    assert {tag["name"] for tag in data["item"]["tags"]} == {"常用", "充电"}
    assert data["item"]["photo_count"] == 1
    assert data["photo"]["has_ai_result"] is True


def test_analyze_without_vision_config_returns_503(client, auth, png_bytes):
    photo = _upload(client, auth, png_bytes)
    response = client.post(
        f"/api/photos/{photo['id']}/analyze", json={}, headers=auth
    )
    assert response.status_code == 503
    assert "视觉模型" in response.get_json()["message"]
