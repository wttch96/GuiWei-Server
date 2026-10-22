"""统计与全局搜索工具。"""
from langchain_core.tools import tool

from app.services import search_service, stats_service
from app.tools.common import fail, guard, ok
from app.utils.errors import ApiError


@tool
def inventory_overview() -> str:
    """查看收纳概览：房间/容器/物品/分类/标签数量、各房间物品分布、最近更新的物品。"""
    return guard(stats_service.overview)


@tool
def global_search(query: str) -> str:
    """跨房间、容器、物品、分类、标签做全局搜索。

    Args:
        query: 搜索关键词。
    """
    try:
        if not (query or "").strip():
            return ok({"hint": "关键词为空"})
        return ok(search_service.search(query))
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"搜索失败：{exc}", 500)
