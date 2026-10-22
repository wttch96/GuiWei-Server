"""管理员模型。系统只有一个管理员，密码以哈希形式存储。"""
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin, utcnow
from app.utils.serialize import iso


class Admin(db.Model, TimestampMixin):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def touch_login(self) -> None:
        self.last_login_at = utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "last_login_at": iso(self.last_login_at),
        }
