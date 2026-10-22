"""统一的业务异常。"""
from typing import Any


class ApiError(Exception):
    """业务异常：会被全局错误处理器转换为统一的 JSON 响应。"""

    def __init__(self, message: str, status: int = 400, data: Any = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.data = data


def not_found(entity: str = "资源") -> ApiError:
    return ApiError(f"{entity}不存在", 404)
