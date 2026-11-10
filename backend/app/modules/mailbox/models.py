"""邮箱游标、扫描租约与可追溯的邮件处理记录。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, TimestampMixin
from app.modules.jobs.constants import ROUND_TYPE_LABELS, STATUS_LABELS


def change_summary(changes: dict | None) -> str | None:
    if not changes:
        return None
    before, after = changes.get("before", {}), changes.get("after", {})
    old, current = before.get("round") or {}, after.get("round") or {}
    parts = []
    created = changes.get("createdPosition")
    if created:
        parts.append(f"新增岗位「{created['position']}」")
    if current and not old:
        parts.append("新增" + ROUND_TYPE_LABELS.get(current.get("roundType"), "轮次"))
    elif current and old.get("result") != current.get("result"):
        labels = {"passed": "通过", "failed": "未通过", "completed": "已完成", "not_started": "未开始",
                  "not_attended": "未参加", "accepted": "已接受", "rejected_offer": "已拒绝"}
        parts.append("结果更新为" + labels.get(current.get("result"), current.get("result", "未知")))
    for key, label in (("startAt", "开始"), ("scheduledAt", "截止")):
        value = current.get(key)
        if value and value != old.get(key):
            parts.append(label + " " + value[:16].replace("T", " "))
    if before.get("status") != after.get("status"):
        parts.append("岗位阶段更新为" + STATUS_LABELS.get(after.get("status"), after.get("status", "未知")))
    return "，".join(parts) if parts else "已核对，岗位和轮次与现有记录一致"


class MailAccount(Base, TimestampMixin):
    __tablename__ = "mail_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(254), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    uid_validity: Mapped[str] = mapped_column(String(40))
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    baseline_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_scan_at: Mapped[datetime] = mapped_column(DateTime)
    scan_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)

    def to_dict(self):
        now = datetime.now()
        return {
            "id": self.id, "address": self.address, "enabled": self.enabled,
            "baselineAt": self.baseline_at.isoformat(),
            "lastScanAt": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "nextScanAt": self.next_scan_at.isoformat() if self.enabled else None,
            "scanning": bool(self.scan_token and self.lease_until and self.lease_until > now),
            "lastError": self.last_error,
        }


class MailMessage(Base, TimestampMixin):
    __tablename__ = "mail_message"
    __table_args__ = (
        UniqueConstraint("account_id", "uid_validity", "uid"),
        UniqueConstraint("account_id", "event_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("mail_account.id"), index=True)
    uid_validity: Mapped[str] = mapped_column(String(40))
    uid: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[str | None] = mapped_column(String(500))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(500))
    sender: Mapped[str] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    body: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    proposal: Mapped[dict | None] = mapped_column(JSON)
    event_key: Mapped[str | None] = mapped_column(String(64))
    processing_token: Mapped[str | None] = mapped_column(String(36))
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("mail_message.id", ondelete="SET NULL"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("application.id", ondelete="SET NULL"))
    round_id: Mapped[int | None] = mapped_column(ForeignKey("interview_round.id", ondelete="SET NULL"))
    changes: Mapped[dict | None] = mapped_column(JSON)

    def to_dict(self, *, detail=False):
        result = {
            "id": self.id, "subject": self.subject, "sender": self.sender,
            "sentAt": self.sent_at.isoformat() if self.sent_at else None,
            "receivedAt": self.received_at.isoformat(), "status": self.status,
            "reason": self.reason, "proposal": self.proposal, "duplicateOf": self.duplicate_of,
            "applicationId": self.application_id, "roundId": self.round_id,
            "changes": self.changes, "attachments": self.attachments,
            "changeSummary": change_summary(self.changes),
        }
        if detail:
            result["body"] = self.body
        return result
