"""独立保存手撕题分类、题目、实现与复盘。"""
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin


class CodingCategory(Base, TimestampMixin):
    __tablename__ = "coding_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class CodingItem(Base, TimestampMixin):
    __tablename__ = "coding_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("coding_category.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    language: Mapped[str] = mapped_column(String(40), default="Python")
    code: Mapped[str] = mapped_column(Text, default="")
    approach: Mapped[str] = mapped_column(Text, default="")
    complexity: Mapped[str] = mapped_column(String(1000), default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    def to_dict(self, *, detail=True):
        data = {"id": self.id, "categoryId": self.category_id, "title": self.title,
                "sourceUrl": self.source_url, "language": self.language, "difficulty": self.difficulty,
                "status": self.status, "tags": self.tags, "createdAt": self.created_at.isoformat(),
                "updatedAt": self.updated_at.isoformat()}
        if detail:
            data.update(description=self.description, code=self.code, approach=self.approach, complexity=self.complexity)
        return data
