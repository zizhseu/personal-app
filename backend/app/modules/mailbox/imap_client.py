"""通过只读 IMAP 获取新增邮件，保留独立的 UID 游标。"""
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime, parseaddr
import hashlib
from html.parser import HTMLParser
import imaplib
import re
import ssl
import unicodedata

from fastapi import HTTPException

from .schemas import local_time

MAX_MAIL_BYTES = 2_000_000
BATCH_SIZE = 50


class HtmlText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def normalized(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def parse_mail(raw: bytes, uid: int, received_at: datetime) -> dict:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    plain, html, attachments = [], [], []
    for part in message.walk():
        if part.get_filename() or part.get_content_disposition() == "attachment":
            attachments.append(str(part.get_filename() or "未命名附件")[:200])
            continue
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        try:
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        (plain if part.get_content_type() == "text/plain" else html).append(text)
    body = "\n".join(plain)
    if not body.strip():
        parser = HtmlText()
        parser.feed("\n".join(html))
        body = "".join(parser.parts)
    # 回复中的旧正文不参与当前招聘事件提取。
    body = re.split(r"(?im)^\s*(?:-{3,}\s*(?:Original Message|原始邮件)|On .+ wrote:)", body)[0]
    subject, sender = str(message.get("subject", "无主题"))[:500], str(message.get("from", ""))[:500]
    sent_at = None
    try:
        sent_at = local_time(parsedate_to_datetime(str(message["date"]))) if message.get("date") else None
    except (ValueError, TypeError, OverflowError):
        pass
    digest = hashlib.sha256(normalized(parseaddr(sender)[1] + "\n" + subject + "\n" + body).encode()).hexdigest()
    truncated = len(raw) > MAX_MAIL_BYTES or len(body) > 60000
    return {
        "uid": uid, "message_id": str(message.get("message-id", ""))[:500] or None,
        "subject": subject, "sender": sender, "body": body[:60000], "fingerprint": digest,
        "sent_at": sent_at, "received_at": received_at, "attachments": attachments[:30],
        "status": "review" if truncated or not body.strip() else "pending",
        "reason": "邮件正文过长或为空，请打开原邮件核对；附件仅记录文件名" if truncated or not body.strip() else None,
    }


def _number(client, key):
    _, values = client.response(key)
    if not values or not values[0] or not re.fullmatch(rb"\d+", values[0]):
        return None
    return int(values[0])


def read_mailbox(address: str, authorization_code: str, *, validity: str | None = None,
                 last_uid: int = 0, through_uid: int | None = None) -> dict:
    client = None
    try:
        client = imaplib.IMAP4_SSL("imap.163.com", 993, ssl_context=ssl.create_default_context(), timeout=25)
        client.login(address, authorization_code)
        # 网易要求声明客户端身份，避免 SELECT 被判定为不安全登录。
        if b"ID" in client.capabilities or "ID" in client.capabilities:
            imaplib.Commands.setdefault("ID", ("AUTH",))
            client._simple_command("ID", '("name" "personal-app" "version" "1.0")')
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise HTTPException(502, "无法以只读方式打开收件箱，请检查 163 的 IMAP 设置")
        validity_number, next_uid = _number(client, "UIDVALIDITY"), _number(client, "UIDNEXT")
        if validity_number is None or next_uid is None:
            # 部分 163 收件箱在 SELECT 响应中省略 UIDNEXT，通过 STATUS 补取。
            cursor_status, cursor_data = client.status("INBOX", "(UIDVALIDITY UIDNEXT)")
            if cursor_status == "OK":
                cursor_text = b" ".join(value for value in cursor_data if isinstance(value, bytes))
                validity_match = re.search(rb"\bUIDVALIDITY\s+(\d+)", cursor_text, re.IGNORECASE)
                next_match = re.search(rb"\bUIDNEXT\s+(\d+)", cursor_text, re.IGNORECASE)
                if validity_number is None and validity_match:
                    validity_number = int(validity_match[1])
                if next_uid is None and next_match:
                    next_uid = int(next_match[1])
        if validity_number is None:
            raise HTTPException(502, "163 未返回收件箱版本标识，暂时无法建立可靠的增量记录")
        if next_uid is None:
            # 仅查询 UID，不读取历史邮件正文；空收件箱的基线为 0。
            search_status, uid_data = client.uid("search", None, "ALL")
            if search_status != "OK":
                raise HTTPException(502, "163 增量游标读取失败，请稍后重试")
            next_uid = max((int(value) for value in (uid_data[0] or b"").split() if value.isdigit()), default=0) + 1
        current_validity = str(validity_number)
        upper_uid = max(0, next_uid - 1)
        # 首次连接或 UIDVALIDITY 变化只建立新基线。
        if validity != current_validity:
            return {"validity": current_validity, "last_uid": upper_uid, "messages": [], "reset": validity is not None, "has_more": False}
        if through_uid is not None:
            upper_uid = min(upper_uid, through_uid)
        status, data = client.uid("search", None, "UID", f"{last_uid + 1}:{max(upper_uid, last_uid + 1)}")
        if status != "OK":
            raise HTTPException(502, "邮箱新增邮件查询失败，游标已保留")
        all_uids = sorted({int(value) for value in (data[0] or b"").split() if value.isdigit() and last_uid < int(value) <= upper_uid})
        uids = all_uids[:BATCH_SIZE]
        messages = []
        for uid in uids:
            status, data = client.uid("fetch", str(uid), f"(INTERNALDATE BODY.PEEK[]<0.{MAX_MAIL_BYTES + 1}>)")
            if status != "OK":
                raise HTTPException(502, "读取新增邮件失败，游标已保留，可以重试")
            parts = [part for part in data if isinstance(part, tuple)]
            if not parts:
                # 扫描期间被用户删除的邮件可跳过，搜索与读取之间存在正常竞争。
                continue
            metadata, raw = parts[0]
            received_at = datetime.now()
            match = re.search(rb'INTERNALDATE "([^"]+)"', metadata)
            if match:
                try:
                    received_at = local_time(datetime.strptime(match[1].decode("ascii"), "%d-%b-%Y %H:%M:%S %z"))
                except ValueError:
                    pass
            messages.append(parse_mail(raw, uid, received_at))
        has_more = len(all_uids) > BATCH_SIZE
        cursor = uids[-1] if has_more else max(last_uid, upper_uid)
        return {"validity": current_validity, "last_uid": cursor, "messages": messages, "reset": False,
                "has_more": has_more, "upper_uid": upper_uid}
    except imaplib.IMAP4.error:
        raise HTTPException(502, "163 邮箱连接失败，请确认已开启 IMAP，并填写客户端授权码") from None
    except (OSError, TimeoutError):
        raise HTTPException(502, "无法连接 163 邮箱，请检查网络后重试") from None
    finally:
        if client is not None:
            try:
                client.logout()
            except (OSError, imaplib.IMAP4.error):
                pass
