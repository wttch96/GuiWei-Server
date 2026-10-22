"""物品大类。一个物品只属于一个分类。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso


class Category(db.Model, TimestampMixin):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="", nullable=False)
    color = db.Column(db.String(16), default="#5b8def", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    items = db.relationship("Item", back_populates="category")

    def to_dict(self, item_count: int | None = None) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "sort_order": self.sort_order,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if item_count is not None:
            data["item_count"] = item_count
        return data
