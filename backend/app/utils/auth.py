"""JWT 签发 / 校验。

Token 通过以下任一方式传递：
  Authorization: Bearer <token>
  X-Auth-Token: <token>
  ?access_token=<token>   （图片等无法设置请求头的场景）
"""
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, jsonify, request

from app.extensions import db
from app.models import Admin
from app.utils.serialize import iso


def create_access_token(admin: Admin) -> tuple[str, int]:
    expires_hours = int(current_app.config["JWT_EXPIRES_HOURS"])
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin.id),
        "username": admin.username,
        "role": "admin",
        "iat": now,
        "exp": now + timedelta(hours=expires_hours),
    }
    token = jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )
    return token, expires_hours * 3600


def extract_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    header_token = request.headers.get("X-Auth-Token")
    if header_token:
        return header_token.strip()
    return request.args.get("access_token") or request.args.get("token")


def _unauthorized(message: str):
    return jsonify({"code": 401, "message": message, "data": None}), 401


def authenticate_request():
    """返回 (admin, error_response)。"""
    token = extract_token()
    if not token:
        return None, _unauthorized("未登录或缺少 Token")
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        return None, _unauthorized("登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        return None, _unauthorized("Token 无效")

    try:
        admin_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return None, _unauthorized("Token 无效")

    admin = db.session.get(Admin, admin_id)
    if not admin:
        return None, _unauthorized("管理员账号不存在")
    return admin, None


def admin_public(admin: Admin) -> dict:
    return {
        "id": admin.id,
        "username": admin.username,
        "created_at": iso(admin.created_at),
        "last_login_at": iso(admin.last_login_at),
    }
