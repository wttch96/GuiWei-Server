"""AI 对话历史。"""
from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.serialize import iso, loads


class AiMessage(db.Model, TimestampMixin):
    __tablename__ = "ai_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)  # user / assistant
    content = db.Column(db.Text, default="", nullable=False)
    tool_trace = db.Column(db.Text, default="", nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "tool_trace": loads(self.tool_trace, []),
            "created_at": iso(self.created_at),
        }
