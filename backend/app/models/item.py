"""物品模型：一个分类 + 多个标签 + 一个位置（房间/容器）。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso

# 物品与标签的多对多中间表
item_tags = db.Table(
    "item_tags",
    db.Column(
        "item_id",
        db.Integer,
        db.ForeignKey("items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

ITEM_STATUSES = {
    "in_stock": "在库",
    "lent": "借出",
    "used_up": "用完",
    "discarded": "已丢弃",
}

# 色系建议值（可选属性；接口不强制，允许自定义）
COLOR_FAMILIES = (
    "黑色",
    "白色",
    "灰色",
    "米色",
    "棕色",
    "红色",
    "橙色",
    "黄色",
    "绿色",
    "青色",
    "蓝色",
    "紫色",
    "粉色",
    "彩色",
    "其他",
)


class Item(db.Model, TimestampMixin):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, default="", nullable=False)
    ai_summary = db.Column(db.Text, default="", nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False, index=True)
    container_id = db.Column(
        db.Integer,
        db.ForeignKey("containers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit = db.Column(db.String(20), default="件", nullable=False)
    status = db.Column(db.String(20), default="in_stock", nullable=False, index=True)
    color_family = db.Column(db.String(20), default="", nullable=False, index=True)
    # 日期均为可选项，空字符串表示未填写；日期格式统一为 YYYY-MM-DD
    purchase_date = db.Column(db.String(20), default="", nullable=False)
    production_date = db.Column(db.String(20), default="", nullable=False)
    valid_period = db.Column(db.String(40), default="", nullable=False)
    expiry_date = db.Column(db.String(20), default="", nullable=False, index=True)

    category = db.relationship("Category", back_populates="items")
    room = db.relationship("Room", back_populates="items")
    container = db.relationship("Container", back_populates="items")
    tags = db.relationship(
        "Tag", secondary=item_tags, back_populates="items", lazy="selectin"
    )
    photos = db.relationship(
        "Photo",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Photo.id",
    )

    def primary_photo(self):
        for photo in self.photos:
            if photo.is_primary:
                return photo
        return self.photos[0] if self.photos else None

    def location_path(self) -> str:
        parts: list[str] = []
        if self.room:
            parts.append(self.room.name)
        if self.container:
            parts.extend(self.container.path_names())
        return " / ".join(parts)

    def to_dict(self, detail: bool = False) -> dict:
        primary = self.primary_photo()
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ai_summary": self.ai_summary,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "room_id": self.room_id,
            "room": {"id": self.room.id, "name": self.room.name} if self.room else None,
            "container_id": self.container_id,
            "container": (
                {
                    "id": self.container.id,
                    "name": self.container.name,
                    "nickname": self.container.nickname or "",
                    "display_name": self.container.display_name,
                }
                if self.container
                else None
            ),
            "location_path": self.location_path(),
            "quantity": self.quantity,
            "unit": self.unit,
            "status": self.status,
            "status_label": ITEM_STATUSES.get(self.status, self.status),
            "color_family": self.color_family or "",
            "purchase_date": self.purchase_date or "",
            "production_date": self.production_date or "",
            "valid_period": self.valid_period or "",
            "expiry_date": self.expiry_date or "",
            "tags": [tag.to_dict() for tag in self.tags],
            "photo_count": len(self.photos),
            "primary_photo": primary.to_dict() if primary else None,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if detail:
            data["photos"] = [photo.to_dict() for photo in self.photos]
        return data
