"""标签相关工具。"""
from langchain_core.tools import tool

from app.services import tag_service
from app.tools.common import guard, ok


@tool
def list_tags() -> str:
    """列出所有标签，包含每个标签的物品数量。"""
    return guard(tag_service.list_tags)


@tool
def create_tag(name: str, color: str = "#8b8b8b") -> str:
    """创建标签。

    Args:
        name: 标签名称，例如「常用」「备用」「冬季」。
        color: 十六进制颜色。
    """
    return guard(tag_service.create_tag, {"name": name, "color": color})


@tool
def update_tag(tag_id: int, name: str | None = None, color: str | None = None) -> str:
    """修改标签。

    Args:
        tag_id: 标签 ID。
        name: 新名称。
        color: 新颜色。
    """
    data = {}
    for key, value in {"name": name, "color": color}.items():
        if value is not None:
            data[key] = value
    return guard(tag_service.update_tag, int(tag_id), data)


@tool
def delete_tag(tag_id: int, confirm: bool = False) -> str:
    """删除标签。危险操作，需要用户明确要求。

    Args:
        tag_id: 标签 ID。
        confirm: 必须显式传 true。
    """
    if not confirm:
        return ok({"deleted": False, "hint": "未执行删除：需要 confirm=true"})
    return guard(tag_service.delete_tag, int(tag_id))
