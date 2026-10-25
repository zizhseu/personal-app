"""新增平台或实现时应遵守的只读采集契约。"""
from dataclasses import dataclass
from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field, field_validator
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Platform:
    id: str
    label: str
    image_hosts: tuple[str, ...]
    referer: str


@dataclass(frozen=True)
class Capabilities:
    sorts: tuple[str, ...] = ("综合", "最新")
    periods: tuple[str, ...] = ("不限",)
    images: bool = True
    subtitles: bool = False
    connection_settings: bool = False
    qr_login: bool = True
    managed_install: bool = True

    def public(self):
        return {"sorts": list(self.sorts), "periods": list(self.periods), "images": self.images,
                "subtitles": self.subtitles, "connectionSettings": self.connection_settings,
                "qrLogin": self.qr_login, "managedInstall": self.managed_install}


class MaterialImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    url: str = Field(default="", max_length=4000)
    status: str = "pending"
    error: str | None = Field(default=None, max_length=500)


class CollectedMaterial(BaseModel):
    """进入整理流程前的统一材料格式，不允许外部字段直接进入 ORM。"""
    model_config = ConfigDict(extra="forbid")
    platform: str = Field(min_length=1, max_length=20)
    source_id: str = Field(min_length=1, max_length=100)
    source_url: str = Field(default="", max_length=2000)
    title: str = Field(default="未命名资料", max_length=300)
    author: str = Field(default="", max_length=100)
    raw_body: str = Field(default="", max_length=60000)
    published_at: str | None = Field(default=None, max_length=40)
    images: list[MaterialImage] = Field(default_factory=list, max_length=30)

    @field_validator("source_url")
    @classmethod
    def valid_source(cls, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError("无效来源链接")
        return value


@dataclass
class SearchResult:
    # meta 是可以展示的字段，locator 只保存在本机私有缓存中。
    meta: dict
    locator: dict


class SourceProvider(Protocol):
    id: str
    platform: str
    label: str
    description: str
    homepage: str
    capabilities: Capabilities

    def availability(self) -> dict: ...
    def connection(self) -> dict: ...
    def save_connection(self, payload: dict) -> dict: ...
    async def start(self) -> dict: ...
    def startup_status(self) -> dict: ...
    async def login_status(self) -> dict: ...
    async def login_qrcode(self) -> dict: ...
    async def search(self, keyword: str, sort: str, period: str) -> list[SearchResult]: ...
    async def fetch(self, locator: dict) -> dict: ...
