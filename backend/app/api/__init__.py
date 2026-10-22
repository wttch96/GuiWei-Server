"""API 蓝图注册。"""
from app.api import (
    ai,
    auth,
    categories,
    containers,
    health,
    items,
    logs,
    photos,
    rooms,
    search,
    stats,
    tags,
)


def register_blueprints(app) -> None:
    for module in (
        health,
        auth,
        rooms,
        containers,
        items,
        categories,
        tags,
        photos,
        ai,
        stats,
        logs,
        search,
    ):
        app.register_blueprint(module.bp)
