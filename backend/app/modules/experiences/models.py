"""独立面经资料；原文、识别材料和 AI 整理分别保存。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin


class ExperienceNote(Base, TimestampMixin):
    __tablename__ = "experience_note"
    __table_args__ = (UniqueConstraint("platform", "source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    title: Mapped[str] = mapped_column(String(300))
    author: Mapped[str] = mapped_column(String(100), default="")
    published_at: Mapped[str | None] = mapped_column(String(40))
    raw_body: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(default=1)
    report: Mapped[dict | None] = mapped_column(JSON)
    report_id: Mapped[str | None] = mapped_column(String(36))
    work_id: Mapped[str | None] = mapped_column(String(36))
    work_kind: Mapped[str | None] = mapped_column(String(20))
    work_status: Mapped[str] = mapped_column(String(20), default="idle")
    work_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(String(500))

    def to_dict(self, *, detail: bool = True) -> dict:
        value = {"id": self.id, "platform": self.platform, "sourceId": self.source_id, "sourceUrl": self.source_url,
                 "title": self.title, "author": self.author, "publishedAt": self.published_at, "revision": self.revision,
                 "imageCount": len(self.images), "questionCount": len((self.report or {}).get("questions", [])),
                 "company": (self.report or {}).get("company"), "position": (self.report or {}).get("position"),
                 "workId": self.work_id, "workKind": self.work_kind, "workStatus": self.work_status, "error": self.error,
                 "updatedAt": self.updated_at.isoformat() if self.updated_at else None}
        if detail:
            value.update(rawBody=self.raw_body, images=self.images, sources=self.sources,
                         report=self.report, reportId=self.report_id)
        return value


class ExperienceExport(Base, TimestampMixin):
    __tablename__ = "experience_export"
    __table_args__ = (UniqueConstraint("note_id", "report_id", "item_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("experience_note.id", ondelete="CASCADE"))
    report_id: Mapped[str] = mapped_column(String(36))
    item_index: Mapped[int]
    qa_id: Mapped[int | None] = mapped_column(ForeignKey("qa_item.id", ondelete="SET NULL"))

    def to_dict(self):
        return {"itemIndex": self.item_index, "reportId": self.report_id, "qaId": self.qa_id}
