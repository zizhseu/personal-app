"""邮件配置、AI 提取结果和人工关联的边界。"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.modules.jobs.constants import ROUND_TYPES
from app.shared.schemas import CamelModel

BEIJING = timezone(timedelta(hours=8))


def local_time(value: datetime) -> datetime:
    return value.astimezone(BEIJING).replace(tzinfo=None) if value.tzinfo else value


class MailSettings(CamelModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(pattern=r"^[A-Za-z0-9_.+-]+@163\.com$", max_length=254)
    authorization_code: str | None = Field(default=None, max_length=128, repr=False)
    enabled: bool = True

    @field_validator("address", mode="before")
    @classmethod
    def normalize_address(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("authorization_code")
    @classmethod
    def normalize_code(cls, value):
        return value.strip() or None if value is not None else None


class CompanySearchResult(CamelModel):
    keyword: str
    companies: list[str]
    has_more: bool = False


class CompanyMatch(CamelModel):
    model_config = ConfigDict(extra="forbid")
    matched_company: str | None = Field(default=None, max_length=100)
    company_match_type: Literal["exact", "alias", "unit", "uncertain"] = "uncertain"
    company_match_reason: str = Field(min_length=1, max_length=1000)
    target_position: str | None = Field(default=None, max_length=100)
    position_action: Literal["existing", "create", "uncertain"] = "uncertain"
    position_match_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("company_match_reason")
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("请提供公司对应依据或待核对原因")
        return value


class MailProposal(CamelModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["event", "reminder", "apply_invitation", "promotion", "unrelated", "uncertain"]
    event_type: Literal["invitation", "result", "reschedule", "offer", "application_received"] | None = None
    company: str | None = Field(default=None, max_length=100)
    matched_company: str | None = Field(default=None, max_length=100)
    company_match_type: Literal["exact", "alias", "unit", "uncertain"] = "uncertain"
    company_match_reason: str | None = Field(default=None, max_length=1000)
    target_position: str | None = Field(default=None, max_length=100)
    position_action: Literal["existing", "create", "uncertain"] = "uncertain"
    position_match_reason: str | None = Field(default=None, max_length=1000)
    company_position_context: list[dict] = Field(default_factory=list)
    company_search_keywords: list[str] = Field(default_factory=list, max_length=5)
    company_search_results: list[CompanySearchResult] = Field(default_factory=list)
    position: str | None = Field(default=None, max_length=100)
    round_type: Literal[ROUND_TYPES] | None = None
    result: Literal["not_started", "completed", "passed", "failed"] | None = None
    start_at: datetime | None = None
    deadline_at: datetime | None = None
    start_evidence: str | None = Field(default=None, max_length=500)
    deadline_evidence: str | None = Field(default=None, max_length=500)
    evidence: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("company_search_keywords")
    @classmethod
    def normalize_keywords(cls, values):
        keywords = list(dict.fromkeys(value.strip() for value in values))
        if any(not value or len(value) > 40 for value in keywords):
            raise ValueError("每个公司检索关键词需为 1 至 40 个字符")
        return keywords

    @field_validator("start_at", "deadline_at")
    @classmethod
    def normalize_datetime(cls, value):
        return local_time(value) if value else value

    @model_validator(mode="after")
    def validate_event(self):
        if self.category == "event" and self.event_type != "application_received":
            if not self.event_type or not self.round_type:
                raise ValueError("招聘事件缺少类型或轮次")
            if self.event_type == "result" and self.result not in ("passed", "failed", "completed"):
                raise ValueError("结果邮件需要明确结果")
            if self.event_type == "offer" and self.round_type not in ("verbal_offer", "formal_offer", "tripartite"):
                raise ValueError("Offer 邮件需要明确 Offer 类型")
            if self.event_type in ("invitation", "reschedule", "offer") and self.result not in (None, "not_started"):
                raise ValueError("邀请和改期不能推断轮次结果")
        if self.start_at and self.deadline_at and self.deadline_at < self.start_at:
            raise ValueError("截止时间早于开始时间")
        return self


class ApplyMessage(CamelModel):
    model_config = ConfigDict(extra="forbid")
    application_id: int = Field(gt=0)
    position_version: int = Field(ge=1)
    position: str | None = Field(max_length=100)
    expected_updated_at: datetime
    expected_snapshot: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    round_id: int | None = Field(default=None, gt=0)
    new_position: str | None = Field(default=None, min_length=1, max_length=100)
    expected_company_snapshot: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_snapshot(self):
        if self.new_position:
            self.new_position = self.new_position.strip()
            if not self.new_position or not self.expected_company_snapshot:
                raise ValueError("新增岗位需要名称和公司记录快照")
        elif not self.expected_snapshot:
            raise ValueError("请选择已有岗位流程")
        return self
