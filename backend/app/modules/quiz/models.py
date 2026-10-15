"""笔试选择题模型：分类与题目。"""
from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TimestampMixin


class QuizCategory(Base, TimestampMixin):
    """笔试选择分类（用户可增删改的实体）。"""

    __tablename__ = "quiz_category"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuizItem(Base, TimestampMixin):
    """一道笔试选择题（单选 / 多选）。"""

    __tablename__ = "quiz_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_category.id", ondelete="RESTRICT"), index=True
    )
    question: Mapped[str] = mapped_column(Text)                 # 题干
    options: Mapped[list[str]] = mapped_column(JSON)            # 选项文本数组（不含 A/B/C 前缀）
    answer: Mapped[list[int]] = mapped_column(JSON)             # 正确选项下标数组（单选 1 个，多选多个）
    qtype: Mapped[str] = mapped_column(String(10), default="single")  # single / multi
    analysis: Mapped[str | None] = mapped_column(Text)          # 解析

    category_rel: Mapped["QuizCategory"] = relationship()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "categoryId": self.category_id,
            "categoryName": self.category_rel.name if self.category_rel else None,
            "question": self.question,
            "options": self.options,
            "answer": self.answer,
            "qtype": self.qtype,
            "analysis": self.analysis,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }