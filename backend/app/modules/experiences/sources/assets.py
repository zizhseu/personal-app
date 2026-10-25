"""下载权限跟随来源平台，不接受任意图片地址或跳转。"""
from urllib.parse import urlsplit, urlunsplit


def image_url(value: str, platform: str = "xiaohongshu") -> str:
    from .registry import get_platform
    try:
        policy = get_platform(platform)
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        if (url.scheme not in {"http", "https"} or url.username is not None or url.password is not None
                or not any(host == suffix or host.endswith("." + suffix) for suffix in policy.image_hosts)
                or url.port not in {None, 80, 443}):
            return ""
        return urlunsplit(("https", host, url.path, url.query, ""))
    except (ValueError, TypeError, AttributeError):
        return ""
