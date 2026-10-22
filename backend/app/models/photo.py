"""照片：可先归档、再挂到物品上；识图结果也存在这里。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso, loads


class Photo(db.Model, TimestampMixin):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(
        db.Integer,
        db.ForeignKey("items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    file_path = db.Column(db.String(255), nullable=False)  # 相对 uploads 的路径
    original_name = db.Column(db.String(255), default="", nullable=False)
    mime_type = db.Column(db.String(64), default="image/jpeg", nullable=False)
    size = db.Column(db.Integer, default=0, nullable=False)
    width = db.Column(db.Integer, default=0, nullable=False)
    height = db.Column(db.Integer, default=0, nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

    ai_text = db.Column(db.Text, default="", nullable=False)   # 模型原始输出
    ai_result = db.Column(db.Text, default="", nullable=False)  # 规范化后的 JSON

    item = db.relationship("Item", back_populates="photos")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "url": f"/api/photos/{self.id}/file",
            "original_name": self.original_name,
            "mime_type": self.mime_type,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
            "ai_result": loads(self.ai_result, None),
            "has_ai_result": bool(self.ai_result),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
