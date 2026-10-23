"""可编辑的 AI 提示词（按 key 覆盖内置默认值）。"""
from app.extensions import db
from app.models.base import TimestampMixin


class AiPrompt(db.Model, TimestampMixin):
    __tablename__ = "ai_prompts"

    key = db.Column(db.String(32), primary_key=True)
    content = db.Column(db.Text, default="", nullable=False)
