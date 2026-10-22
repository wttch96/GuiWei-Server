"""容器 API。"""
from flask import Blueprint

from app.schemas.common import int_arg, parse_body
from app.schemas.storage import ContainerIn, ContainerMove, ContainerUpdate
from app.services import container_service
from app.utils.responses import ok

bp = Blueprint("containers", __name__, url_prefix="/api")


@bp.get("/containers")
def list_containers():
    room_id = int_arg("room_id")
    if room_id:
        return ok(container_service.list_containers(room_id))
    from app.models import Container

    return ok([row.to_dict() for row in Container.query.order_by(Container.id.asc()).all()])


@bp.get("/containers/tree")
def container_tree():
    room_id = int_arg("room_id")
    if not room_id:
        return ok({"tree": []})
    return ok({"room_id": room_id, "tree": container_service.list_tree(room_id)})


@bp.post("/containers")
def create_container():
    body = parse_body(ContainerIn)
    return ok(container_service.create_container(body.model_dump()), status=201)


@bp.get("/containers/<int:container_id>")
def get_container(container_id: int):
    container = container_service.get_container(container_id)
    return ok(
        {
            **container.to_dict(),
            "path": container_service.container_path(container),
        }
    )


@bp.put("/containers/<int:container_id>")
def update_container(container_id: int):
    body = parse_body(ContainerUpdate)
    return ok(container_service.update_container(container_id, body.model_dump(exclude_unset=True)))


@bp.post("/containers/<int:container_id>/move")
def move_container(container_id: int):
    body = parse_body(ContainerMove)
    return ok(
        container_service.move_container(
            container_id, body.target_room_id, body.target_parent_id
        )
    )


@bp.delete("/containers/<int:container_id>")
def delete_container(container_id: int):
    container_service.delete_container(container_id)
    return ok({"deleted": True})
