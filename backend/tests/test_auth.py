def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["data"]["database"] == "ok"


def test_protected_route_requires_token(client):
    response = client.get("/api/rooms")
    assert response.status_code == 401
    assert response.get_json()["code"] == 401


def test_login_wrong_password(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_and_me(client, token):
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["data"]["username"] == "admin"


def test_change_password(client, auth):
    response = client.post(
        "/api/auth/change-password",
        json={"old_password": "admin123", "new_password": "newpass456"},
        headers=auth,
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "newpass456"}
        ).status_code
        == 200
    )


def test_cannot_create_second_admin(app):
    from app.services import admin_service
    from app.utils.errors import ApiError

    with app.app_context():
        try:
            admin_service.create_admin("other", "secret123")
            raise AssertionError("应当拒绝创建第二个管理员")
        except ApiError as exc:
            assert exc.status == 409
