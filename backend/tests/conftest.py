import io

import pytest
from PIL import Image

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///"
            + (tmp_path / "test.db").as_posix(),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SECRET_KEY": "s" * 40,
            "JWT_SECRET": "j" * 40,
            "JWT_EXPIRES_HOURS": 1,
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "admin123",
            "AUTO_CREATE_DB": True,
            "AUTO_BOOTSTRAP_ADMIN": True,
            "DEEPSEEK_API_KEY": "",
            "VISION_API_KEY": "",
            "VISION_MODEL": "",
        }
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def token(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["token"]


@pytest.fixture()
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), (20, 180, 140)).save(buffer, format="PNG")
    return buffer.getvalue()


def create_room(client, auth, name="客厅"):
    response = client.post("/api/rooms", json={"name": name}, headers=auth)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def create_container(client, auth, room_id, name="电视柜", parent_id=None):
    response = client.post(
        "/api/containers",
        json={"room_id": room_id, "name": name, "parent_id": parent_id},
        headers=auth,
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]
