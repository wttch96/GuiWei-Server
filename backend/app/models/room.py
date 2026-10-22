"""房间：收纳层级的第一层。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso


class Room(db.Model, TimestampMixin):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="", nullable=False)
    color = db.Column(db.String(16), default="#2f7d6d", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    containers = db.relationship(
        "Container",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="Container.sort_order, Container.id",
    )
    items = db.relationship("Item", back_populates="room")

    def to_dict(self, item_count: int | None = None, container_count: int | None = None) -> dict:
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
        if container_count is not None:
            data["container_count"] = container_count
        return data
