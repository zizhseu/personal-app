"""面试八股模型：分类实体与问答。"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TimestampMixin


class QaCategory(Base, TimestampMixin):
    """面试八股分类（用户可增删改的实体）。"""

    __tablename__ = "qa_category"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class QaItem(Base, TimestampMixin):
    """一条面试八股问答。"""

    __tablename__ = "qa_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("qa_category.id", ondelete="RESTRICT"), index=True
    )
    question: Mapped[str] = mapped_column(String(500))             # 问题
    answer: Mapped[str | None] = mapped_column(Text)               # 答案要点
    tags: Mapped[list[str] | None] = mapped_column(JSON)           # 自定义标签（多选）
    status: Mapped[str] = mapped_column(String(20), default="learning")  # 掌握状态
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime)      # 最后阅读时间
    related_ids: Mapped[list[int] | None] = mapped_column(JSON)    # 手动相关题目（有向：我指向的 id 列表）
    # 旧分类字符串列（已废弃，仅保留历史数据）

    category_rel: Mapped["QaCategory"] = relationship()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "categoryId": self.category_id,
            "categoryName": self.category_rel.name if self.category_rel else None,
            "question": self.question,
            "answer": self.answer,
            "tags": self.tags,
            "relatedIds": self.related_ids,
            "status": self.status,
            "lastReadAt": self.last_read_at.isoformat() if self.last_read_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }