"""容器：柜子、抽屉、收纳盒……支持任意层级（parent_id 自关联）。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso


class Container(db.Model, TimestampMixin):
    __tablename__ = "containers"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False, index=True)
    parent_id = db.Column(
        db.Integer, db.ForeignKey("containers.id"), nullable=True, index=True
    )
    name = db.Column(db.String(80), nullable=False)
    nickname = db.Column(db.String(80), default="", nullable=False)
    code = db.Column(db.String(40), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    room = db.relationship("Room", back_populates="containers")
    parent = db.relationship(
        "Container", remote_side=[id], back_populates="children"
    )
    children = db.relationship(
        "Container",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Container.sort_order, Container.id",
    )
    items = db.relationship("Item", back_populates="container")

    @property
    def display_name(self) -> str:
        """展示名称：有昵称时显示为「柜子A（药柜）」。"""
        return f"{self.name}（{self.nickname}）" if self.nickname else self.name

    def path_names(self) -> list[str]:
        """从顶层容器到当前容器的名称列表。"""
        names: list[str] = []
        node = self
        seen: set[int] = set()
        while node is not None and node.id not in seen:
            seen.add(node.id)
            names.append(node.display_name)
            node = node.parent
        return list(reversed(names))

    def to_dict(self, item_count: int | None = None) -> dict:
        data = {
            "id": self.id,
            "room_id": self.room_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "nickname": self.nickname or "",
            "display_name": self.display_name,
            "code": self.code,
            "description": self.description,
            "sort_order": self.sort_order,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if self.room:
            data["room_name"] = self.room.name
        if item_count is not None:
            data["item_count"] = item_count
        return data
