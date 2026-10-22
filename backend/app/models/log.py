"""操作日志：记录 API / AI 对数据的改动。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso, loads


class OperationLog(db.Model, TimestampMixin):
    __tablename__ = "operation_logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(32), default="", nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, default="", nullable=False)
    source = db.Column(db.String(16), default="api", nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "detail": loads(self.detail, self.detail),
            "source": self.source,
            "created_at": iso(self.created_at),
        }
