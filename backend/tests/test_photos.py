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


def test_photo_library_pagination_filter_and_summary(client, auth, png_bytes):
    room = create_room(client, auth)
    item = client.post(
        "/api/items", json={"name": "蓝牙耳机", "room_id": room["id"]}, headers=auth
    ).get_json()["data"]
    attached = _upload(client, auth, png_bytes)
    _upload(client, auth, png_bytes)
    client.post(
        f"/api/photos/{attached['id']}/attach",
        json={"item_id": item["id"]},
        headers=auth,
    )

    page = client.get(
        "/api/photos?page=1&page_size=1", headers=auth
    ).get_json()["data"]
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert "ai_result" not in page["items"][0]
    assert page["summary"]["count"] == 2
    assert page["summary"]["unattached_count"] == 1
    assert page["summary"]["size"] > 0

    linked = client.get(
        "/api/photos?status=attached", headers=auth
    ).get_json()["data"]
    assert linked["total"] == 1
    assert linked["items"][0]["item_name"] == "蓝牙耳机"

    orphans = client.get(
        "/api/photos?status=unattached", headers=auth
    ).get_json()["data"]
    assert orphans["total"] == 1
    assert orphans["items"][0]["item_name"] is None

    assert client.get("/api/photos?q=test", headers=auth).get_json()["data"]["total"] == 2
    assert client.get("/api/photos?q=missing", headers=auth).get_json()["data"]["total"] == 0

    # 指定 item_id 时仍返回旧的数组结构
    by_item = client.get(
        f"/api/photos?item_id={item['id']}", headers=auth
    ).get_json()["data"]
    assert isinstance(by_item, list) and len(by_item) == 1


def test_batch_delete_photos_and_promote_primary(client, auth, png_bytes, token):
    room = create_room(client, auth)
    item = client.post(
        "/api/items", json={"name": "相机", "room_id": room["id"]}, headers=auth
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

    response = client.post(
        "/api/photos/batch-delete", json={"ids": [first["id"], 99999]}, headers=auth
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["deleted"] == 1
    assert response.get_json()["data"]["missing"] == [99999]

    detail = client.get(f"/api/items/{item['id']}", headers=auth).get_json()["data"]
    assert detail["photo_count"] == 1
    assert detail["primary_photo"]["id"] == second["id"]
    assert client.get(
        f"/api/photos/{first['id']}/file?token={token}", headers=auth
    ).status_code == 404

    assert client.post(
        "/api/photos/batch-delete", json={"ids": []}, headers=auth
    ).status_code == 422
    assert client.post(
        "/api/photos/batch-delete", json={"ids": [99999]}, headers=auth
    ).status_code == 404


def test_photo_download_disposition(client, auth, png_bytes, token):
    photo = _upload(client, auth, png_bytes)
    response = client.get(
        f"/api/photos/{photo['id']}/file?token={token}&download=1"
    )
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]


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
        "color_family": "白色",
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
    assert data["item"]["color_family"] == "白色"
    assert data["item"]["photo_count"] == 1
    assert data["photo"]["has_ai_result"] is True


def test_analyze_returns_similar_items(client, auth, png_bytes, monkeypatch):
    from app.services import vision_service

    room = create_room(client, auth)
    target = client.post(
        "/api/items",
        json={
            "name": "电视遥控器",
            "room_id": room["id"],
            "description": "黑色长条形电视遥控器，塑料材质",
            "category_name": "电子产品",
            "tag_names": ["遥控器", "客厅"],
        },
        headers=auth,
    ).get_json()["data"]
    unrelated = client.post(
        "/api/items",
        json={
            "name": "折叠雨伞",
            "room_id": room["id"],
            "description": "黑色折叠雨伞，晴雨两用",
            "category_name": "日用品",
            "tag_names": ["雨天"],
        },
        headers=auth,
    ).get_json()["data"]
    photo = _upload(client, auth, png_bytes)
    suggestion = {
        "name": "遥控器",
        "description": "黑色长条形电视遥控器，塑料材质",
        "category": "电子产品",
        "tags": ["遥控器"],
        "quantity": 1,
        "location_hint": "客厅/电视柜",
        "confidence": 0.9,
        "raw_text": "",
        "raw_content": "{}",
    }

    def fake_analyze(photo_obj):
        photo_obj.ai_text = json.dumps(suggestion, ensure_ascii=False)
        photo_obj.ai_result = json.dumps(suggestion, ensure_ascii=False)
        return suggestion

    monkeypatch.setattr(vision_service, "analyze_photo", fake_analyze)

    response = client.post(f"/api/photos/{photo['id']}/analyze", headers=auth)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    names = [row["name"] for row in data["similar_items"]]
    assert "电视遥控器" in names
    assert unrelated["name"] not in names
    top = data["similar_items"][0]
    assert top["id"] == target["id"]
    assert top["similarity"] >= 0.5
    assert top["match_reasons"]

    # 已有识图结果时，可单独重新匹配（物品数据变化后也能刷新）
    similar = client.post(
        f"/api/photos/{photo['id']}/similar", json={"limit": 3}, headers=auth
    )
    assert similar.status_code == 200, similar.get_json()
    payload = similar.get_json()["data"]
    assert payload["suggestion"]["name"] == "遥控器"
    assert payload["items"][0]["id"] == target["id"]


def test_similar_requires_analysis(client, auth, png_bytes):
    photo = _upload(client, auth, png_bytes)
    response = client.post(
        f"/api/photos/{photo['id']}/similar", json={}, headers=auth
    )
    assert response.status_code == 422
    assert "识图" in response.get_json()["message"]


def test_analyze_without_json_body(client, auth, png_bytes, monkeypatch):
    """前端不传 body 时也应使用默认参数，而不是报“请求体必须是 JSON”。"""
    from app.services import vision_service

    photo = _upload(client, auth, png_bytes)
    suggestion = {
        "name": "遥控器",
        "description": "黑色遥控器",
        "category": "电子产品",
        "tags": ["遥控器"],
        "quantity": 1,
        "location_hint": "客厅/电视柜",
        "confidence": 0.9,
        "raw_text": "",
        "raw_content": "{}",
    }
    monkeypatch.setattr(
        vision_service, "analyze_photo", lambda photo_obj: suggestion
    )

    response = client.post(f"/api/photos/{photo['id']}/analyze", headers=auth)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["suggestion"]["name"] == "遥控器"


def test_analyze_without_vision_config_returns_503(client, auth, png_bytes):
    photo = _upload(client, auth, png_bytes)
    response = client.post(
        f"/api/photos/{photo['id']}/analyze", json={}, headers=auth
    )
    assert response.status_code == 503
    assert "视觉模型" in response.get_json()["message"]


def test_vision_uses_deepseek_multimodal_payload(
    client, auth, png_bytes, app, monkeypatch
):
    from app.services import photo_service, vision_service

    app.config.update(
        VISION_API_BASE="https://api.deepseek.com",
        VISION_API_KEY="sk-test",
        VISION_MODEL="deepseek-flash",
    )
    photo = _upload(client, auth, png_bytes)
    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            content = json.dumps(
                {
                    "name": "测试物品",
                    "description": "测试描述",
                    "category": "日用品",
                    "tags": ["测试"],
                    "quantity": 1,
                    "location_hint": "客厅/抽屉",
                    "confidence": 0.8,
                    "raw_text": "",
                },
                ensure_ascii=False,
            )
            return {"choices": [{"message": {"content": content}}]}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(vision_service.requests, "post", fake_post)

    with app.app_context():
        result = vision_service.analyze_photo(photo_service.get_photo(photo["id"]))

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["payload"]["model"] == "deepseek-flash"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    blocks = captured["payload"]["messages"][0]["content"]
    assert blocks[0]["type"] == "text"
    assert "color_family" in blocks[0]["text"]
    assert blocks[1]["type"] == "image_url"
    assert blocks[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result["name"] == "测试物品"


def test_normalize_color_family():
    from app.services.vision_service import normalize_color_family

    assert normalize_color_family("黑色") == "黑色"
    assert normalize_color_family("深蓝色") == "蓝色"
    assert normalize_color_family("银灰") == "灰色"
    assert normalize_color_family("米白") == "白色"
    assert normalize_color_family("多色花纹") == "彩色"
    assert normalize_color_family("透明") == "其他"
    assert normalize_color_family("") == ""
    assert normalize_color_family(None) == ""
