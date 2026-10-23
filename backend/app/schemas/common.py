"""Pydantic 请求校验与统一错误转换。"""
from typing import TypeVar

from flask import request
from pydantic import BaseModel, ConfigDict, ValidationError

from app.utils.errors import ApiError

T = TypeVar("T", bound=BaseModel)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


def parse_body(model_cls: type[T], optional: bool = False) -> T:
    payload = request.get_json(silent=True)
    if payload is None:
        # 允许没有请求体的接口（字段均有默认值）省略 JSON body
        if optional and not request.content_length:
            payload = {}
        else:
            raise ApiError("请求体必须是 JSON", 400)
    if not isinstance(payload, dict):
        raise ApiError("请求体必须是 JSON 对象", 400)
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "body"
        raise ApiError(f"参数校验失败：{location} {first.get('msg', '')}", 422) from exc


def int_arg(name: str, default: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError(f"参数 {name} 必须是整数", 422) from exc


def bool_arg(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
