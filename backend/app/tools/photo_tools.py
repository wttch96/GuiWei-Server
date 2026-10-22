"""照片识图工具。"""
from langchain_core.tools import tool

from app.extensions import db
from app.services import item_service, photo_service, vision_service
from app.tools.common import fail, ok
from app.utils.errors import ApiError


@tool
def recognize_photo(photo_id: int | None = None, item_id: int | None = None) -> str:
    """对已上传的照片做视觉识别，返回物品名称、分类、标签、数量等建议。
    识别结果会保存到照片记录；如需真正创建物品，再调用 create_item。

    Args:
        photo_id: 照片 ID。
        item_id: 物品 ID；不传 photo_id 时，识别该物品的第一张照片。
    """
    try:
        if photo_id:
            photo = photo_service.get_photo(int(photo_id))
        elif item_id:
            item = item_service.get_item(int(item_id))
            photo = item.primary_photo()
            if not photo:
                return fail("该物品还没有照片")
        else:
            return fail("需要提供 photo_id 或 item_id")
        result = vision_service.analyze_photo(photo)
        db.session.commit()
        return ok({"photo_id": photo.id, "item_id": photo.item_id, "suggestion": result})
    except ApiError as exc:
        return fail(exc.message, exc.status)
    except Exception as exc:
        return fail(f"识图失败：{exc}", 500)
