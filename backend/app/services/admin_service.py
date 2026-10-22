"""管理员服务。系统仅保留一个管理员账号。"""
from flask import current_app

from app.extensions import db
from app.models import Admin
from app.utils.errors import ApiError


def get_admin(admin_id: int) -> Admin:
    admin = db.session.get(Admin, admin_id)
    if not admin:
        raise ApiError("管理员不存在", 404)
    return admin


def get_by_username(username: str) -> Admin | None:
    return Admin.query.filter_by(username=username).first()


def create_admin(username: str, password: str) -> Admin:
    username = (username or "").strip()
    if not username:
        raise ApiError("管理员用户名不能为空")
    if len(password or "") < 6:
        raise ApiError("密码至少 6 位")
    if Admin.query.count() > 0:
        raise ApiError("管理员已存在，系统只允许一个管理员", 409)
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin


def bootstrap_admin() -> Admin | None:
    """数据库为空且配置了账号密码时，自动创建第一个管理员。"""
    if Admin.query.count() > 0:
        return None
    username = (current_app.config.get("ADMIN_USERNAME") or "").strip()
    password = current_app.config.get("ADMIN_PASSWORD") or ""
    if not username or not password:
        return None
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    current_app.logger.info("已创建初始管理员: %s", username)
    return admin


def login(username: str, password: str) -> Admin:
    admin = get_by_username((username or "").strip())
    if not admin or not admin.check_password(password or ""):
        raise ApiError("用户名或密码错误", 401)
    admin.touch_login()
    db.session.commit()
    return admin


def change_password(admin: Admin, old_password: str, new_password: str) -> None:
    if not admin.check_password(old_password or ""):
        raise ApiError("原密码不正确", 400)
    if len(new_password or "") < 6:
        raise ApiError("新密码至少 6 位")
    admin.set_password(new_password)
    db.session.commit()


def reset_password(username: str, new_password: str) -> Admin:
    admin = get_by_username(username)
    if not admin:
        raise ApiError("管理员不存在", 404)
    if len(new_password or "") < 6:
        raise ApiError("密码至少 6 位")
    admin.set_password(new_password)
    db.session.commit()
    return admin
