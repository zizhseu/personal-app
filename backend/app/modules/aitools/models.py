"""简历、面试会话、对话及复盘导入记录。"""
from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin


class ResumeDocument(Base, TimestampMixin):
    __tablename__ = "ai_resume"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)

    def to_dict(self, *, include_content: bool = True) -> dict:
        result = {"id": self.id, "name": self.name, "updatedAt": self.updated_at.isoformat()}
        if include_content:
            result["content"] = self.content
        return result


class InterviewSession(Base, TimestampMixin):
    __tablename__ = "ai_interview_session"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("ai_resume.id", ondelete="SET NULL"))
    resume_name: Mapped[str] = mapped_column(String(100))
    resume_content: Mapped[str] = mapped_column(Text)
    target_role: Mapped[str] = mapped_column(String(100), default="")
    focus: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    pending_operation_id: Mapped[str | None] = mapped_column(String(36))
    report: Mapped[dict | None] = mapped_column(JSON)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "resumeId": self.resume_id, "resumeName": self.resume_name,
            "targetRole": self.target_role, "focus": self.focus, "status": self.status,
            "createdAt": self.created_at.isoformat(), "updatedAt": self.updated_at.isoformat(),
        }


class InterviewOperation(Base, TimestampMixin):
    """一次逻辑请求；重复提交与失败重试复用同一标识。"""
    __tablename__ = "ai_interview_operation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("ai_interview_session.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    attempt_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status, "error": self.error}


class InterviewMessage(Base, TimestampMixin):
    __tablename__ = "ai_interview_message"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("ai_interview_session.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("ai_interview_operation.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {"id": self.id, "role": self.role, "content": self.content,
                "operationId": self.operation_id, "createdAt": self.created_at.isoformat()}


class ReviewAction(Base, TimestampMixin):
    __tablename__ = "ai_review_action"
    __table_args__ = (UniqueConstraint("session_id", "item_index", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("ai_interview_session.id", ondelete="CASCADE"), index=True)
    item_index: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    qa_id: Mapped[int | None] = mapped_column(ForeignKey("qa_item.id", ondelete="SET NULL"))
    todo_id: Mapped[int | None] = mapped_column(ForeignKey("todo_item.id", ondelete="SET NULL"))

    def to_dict(self) -> dict:
        return {"itemIndex": self.item_index, "kind": self.kind, "targetId": self.qa_id if self.kind == "qa" else self.todo_id}
