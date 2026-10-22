"""分类相关工具。"""
from langchain_core.tools import tool

from app.services import category_service
from app.tools.common import guard, ok


@tool
def list_categories() -> str:
    """列出所有物品大类，包含每类物品数量。"""
    return guard(category_service.list_categories)


@tool
def create_category(name: str, description: str = "", color: str = "#5b8def") -> str:
    """创建物品大类。一个物品只能属于一个分类。

    Args:
        name: 分类名称，例如「电子产品」「日用品」。
        description: 分类描述。
        color: 十六进制颜色。
    """
    return guard(
        category_service.create_category,
        {"name": name, "description": description, "color": color},
    )


@tool
def update_category(
    category_id: int,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
) -> str:
    """修改分类信息。

    Args:
        category_id: 分类 ID。
        name: 新名称。
        description: 新描述。
        color: 新颜色。
    """
    data = {}
    for key, value in {"name": name, "description": description, "color": color}.items():
        if value is not None:
            data[key] = value
    return guard(category_service.update_category, int(category_id), data)


@tool
def delete_category(category_id: int, confirm: bool = False) -> str:
    """删除分类（该分类下的物品会变为未分类）。危险操作，需要用户明确要求。

    Args:
        category_id: 分类 ID。
        confirm: 必须显式传 true。
    """
    if not confirm:
        return ok({"deleted": False, "hint": "未执行删除：需要 confirm=true"})
    return guard(category_service.delete_category, int(category_id))
