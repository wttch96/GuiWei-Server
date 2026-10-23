"""房间 / 容器 / 物品 / 分类 / 标签的请求模型。"""
from pydantic import Field

from app.schemas.common import APIModel


class RoomIn(APIModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    color: str = "#2f7d6d"
    sort_order: int = 0


class RoomUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    color: str | None = None
    sort_order: int | None = None


class ContainerIn(APIModel):
    room_id: int
    name: str = Field(min_length=1, max_length=80)
    nickname: str = Field(default="", max_length=80)
    parent_id: int | None = None
    code: str = ""
    description: str = ""
    sort_order: int = 0


class ContainerUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    nickname: str | None = Field(default=None, max_length=80)
    code: str | None = None
    description: str | None = None
    sort_order: int | None = None


class ContainerMove(APIModel):
    target_room_id: int
    target_parent_id: int | None = None


class ItemIn(APIModel):
    name: str = Field(min_length=1, max_length=200)
    room_id: int | None = None
    room_name: str | None = None
    container_id: int | None = None
    container_path: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    tag_ids: list[int] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)
    description: str = ""
    ai_summary: str = ""
    quantity: int = Field(default=1, ge=0)
    unit: str = "件"
    status: str = "in_stock"
    color_family: str = Field(default="", max_length=20)
    photo_ids: list[int] = Field(default_factory=list)


class ItemUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    ai_summary: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    unit: str | None = None
    status: str | None = None
    color_family: str | None = Field(default=None, max_length=20)
    category_id: int | None = None
    category_name: str | None = None
    tag_ids: list[int] | None = None
    tag_names: list[str] | None = None
    room_id: int | None = None
    room_name: str | None = None
    container_id: int | None = None
    container_path: str | None = None
    photo_ids: list[int] | None = None


class ItemMove(APIModel):
    room_id: int | None = None
    room_name: str | None = None
    container_id: int | None = None
    container_path: str | None = None


class CategoryIn(APIModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    color: str = "#5b8def"
    sort_order: int = 0


class CategoryUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    color: str | None = None
    sort_order: int | None = None


class TagIn(APIModel):
    name: str = Field(min_length=1, max_length=40)
    color: str = "#8b8b8b"


class TagUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = None


class PhotoAttachIn(APIModel):
    item_id: int


class PhotoAnalyzeIn(APIModel):
    create_item: bool = False
    room_id: int | None = None
    room_name: str | None = None
    container_id: int | None = None
    category_id: int | None = None
    category_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    name: str | None = None
    description: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    color_family: str | None = Field(default=None, max_length=20)


class PhotoSimilarIn(APIModel):
    limit: int = Field(default=6, ge=1, le=20)


class PhotoBatchDeleteIn(APIModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class ChatIn(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)


class PromptUpdateIn(APIModel):
    content: str = Field(min_length=20, max_length=20000)
