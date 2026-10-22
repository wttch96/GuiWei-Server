"""标签。物品与标签是多对多关系。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso


class Tag(db.Model, TimestampMixin):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False, index=True)
    color = db.Column(db.String(16), default="#8b8b8b", nullable=False)

    items = db.relationship(
        "Item", secondary="item_tags", back_populates="tags", lazy="selectin"
    )

    def to_dict(self, item_count: int | None = None) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if item_count is not None:
            data["item_count"] = item_count
        return data
