"""登录 / 当前管理员 / 修改密码。"""
from flask import Blueprint, g

from app.extensions import db
from app.schemas.auth import ChangePasswordIn, LoginIn
from app.schemas.common import parse_body
from app.services import admin_service, log_service
from app.utils.auth import admin_public, create_access_token
from app.utils.responses import ok

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    body = parse_body(LoginIn)
    admin = admin_service.login(body.username, body.password)
    token, expires_in = create_access_token(admin)
    log_service.record("login", "admin", admin.id, {"username": admin.username})
    db.session.commit()
    return ok(
        {
            "token": token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "admin": admin_public(admin),
        }
    )


@bp.get("/me")
def me():
    return ok(admin_public(g.admin))


@bp.post("/change-password")
def change_password():
    body = parse_body(ChangePasswordIn)
    admin_service.change_password(g.admin, body.old_password, body.new_password)
    log_service.record("change_password", "admin", g.admin.id)
    db.session.commit()
    return ok({"changed": True})
