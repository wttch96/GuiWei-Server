"""所有模型统一导出，确保 SQLAlchemy 能解析关系。"""
from app.models.admin import Admin
from app.models.ai_message import AiMessage
from app.models.category import Category
from app.models.container import Container
from app.models.item import COLOR_FAMILIES, ITEM_STATUSES, Item, item_tags
from app.models.log import OperationLog
from app.models.photo import Photo
from app.models.room import Room
from app.models.tag import Tag

__all__ = [
    "Admin",
    "AiMessage",
    "Category",
    "COLOR_FAMILIES",
    "Container",
    "Item",
    "ITEM_STATUSES",
    "item_tags",
    "OperationLog",
    "Photo",
    "Room",
    "Tag",
]
