"""配置、任务租约、增量收件与原生 AI 处理。"""
from datetime import datetime, timedelta
import re
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import private_store
from app.core.database import SessionLocal

from . import analysis, execution, imap_client
from .models import MailAccount, MailMessage
from .schemas import CompanySearchResult, MailSettings

SCAN_INTERVAL = timedelta(hours=1)
LEASE_SECONDS = 300
SECRET_FILE = "mailbox.private"


def current_account(db: Session) -> MailAccount | None:
    return db.scalar(select(MailAccount).where(MailAccount.active.is_(True)).order_by(MailAccount.id.desc()))


def authorization_code(address: str) -> str:
    return private_store.read_document(SECRET_FILE).get(address, "")


def public_settings(db: Session) -> dict:
    account = current_account(db)
    return {"account": account.to_dict() if account else None, "intervalMinutes": 60,
            "authorizationConfigured": bool(authorization_code(account.address)) if account else False}


async def test_connection(data: MailSettings) -> dict:
    code = data.authorization_code or await run_in_threadpool(authorization_code, data.address)
    if not code:
        raise HTTPException(400, "请填写 163 客户端授权码")
    return await run_in_threadpool(imap_client.read_mailbox, data.address, code)


async def save_settings(db: Session, data: MailSettings) -> dict:
    account = current_account(db)
    if account and account.to_dict()["scanning"]:
        raise HTTPException(409, "正在扫描邮箱，请等待本次任务结束后修改配置")
    baseline = await test_connection(data)
    # 网络验证完成后再锁定数据库，避免在等待邮箱时持有写锁。
    account = current_account(db)
    if account and account.to_dict()["scanning"]:
        raise HTTPException(409, "正在扫描邮箱，请等待本次任务结束后修改配置")
    if data.authorization_code:
        with private_store.LOCK:
            document = private_store.read_document(SECRET_FILE)
            document[data.address] = data.authorization_code
            private_store.write_document(SECRET_FILE, document)
    account = db.scalar(select(MailAccount).where(MailAccount.address == data.address))
    now = datetime.now()
    if account is None:
        account = MailAccount(address=data.address, uid_validity=baseline["validity"], last_uid=baseline["last_uid"],
                              baseline_at=now, next_scan_at=now + SCAN_INTERVAL)
        db.add(account)
    elif account.uid_validity != baseline["validity"]:
        account.uid_validity, account.last_uid, account.baseline_at = baseline["validity"], baseline["last_uid"], now
    db.execute(update(MailAccount).values(active=False, enabled=False, scan_token=None, lease_until=None))
    account.active, account.enabled = True, data.enabled
    account.next_scan_at, account.last_error = now + SCAN_INTERVAL, None
    db.commit()
    db.refresh(account)
    return public_settings(db)


def claim_scan(db: Session, account_id: int, *, scheduled: bool = False) -> str:
    now, token = datetime.now(), str(uuid4())
    filters = [MailAccount.id == account_id, MailAccount.active.is_(True),
               or_(MailAccount.scan_token.is_(None), MailAccount.lease_until <= now)]
    values = {"scan_token": token, "lease_until": now + timedelta(seconds=LEASE_SECONDS), "last_error": None}
    if scheduled:
        filters.extend([MailAccount.enabled.is_(True), MailAccount.next_scan_at <= now])
        values["next_scan_at"] = now + SCAN_INTERVAL
    claimed = db.execute(update(MailAccount).where(*filters).values(**values))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "邮箱正在扫描或定时任务尚未到期，请稍后查看")
    db.commit()
    return token


def renew_lease(db: Session, account_id: int, token: str) -> None:
    updated = db.execute(update(MailAccount).where(MailAccount.id == account_id, MailAccount.scan_token == token)
                         .values(lease_until=datetime.now() + timedelta(seconds=LEASE_SECONDS)))
    if updated.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "本次扫描租约已失效，结果由较新的扫描接管")
    db.commit()


def store_batch(db: Session, account_id: int, token: str, batch: dict) -> None:
    renew_lease(db, account_id, token)
    account = db.get(MailAccount, account_id)
    if batch["reset"]:
        account.baseline_at = datetime.now()
        account.last_error = "邮箱增量标识发生变化，已重新建立基线，从此刻的新邮件继续处理"
    for payload in batch["messages"]:
        exists = db.scalar(select(MailMessage.id).where(MailMessage.account_id == account_id,
            MailMessage.uid_validity == batch["validity"], MailMessage.uid == payload["uid"]))
        if exists:
            continue
        duplicate = db.scalar(select(MailMessage).where(MailMessage.account_id == account_id,
            MailMessage.fingerprint == payload["fingerprint"]).order_by(MailMessage.id).limit(1))
        if duplicate:
            payload = {**payload, "status": "duplicate", "reason": "与已收取邮件内容相同，已跳过重复处理", "duplicate_of": duplicate.id}
        db.add(MailMessage(account_id=account_id, uid_validity=batch["validity"], **payload))
        db.flush()
    account.uid_validity, account.last_uid = batch["validity"], batch["last_uid"]
    account.last_scan_at = datetime.now()
    db.commit()


def finish_message(db: Session, message_id: int, token: str, status: str, reason: str) -> None:
    owned_accounts = select(MailAccount.id).where(MailAccount.scan_token == token)
    db.execute(update(MailMessage).where(MailMessage.id == message_id, MailMessage.processing_token == token,
                                        MailMessage.account_id.in_(owned_accounts))
               .values(status=status, reason=reason[:1000], processing_token=None))
    db.commit()


async def analyze_message(db: Session, message_id: int, token: str) -> None:
    message = db.get(MailMessage, message_id)
    renew_lease(db, message.account_id, token)
    message.status, message.processing_token = "analyzing", token
    db.commit()
    if (re.search(r"职位推荐|岗位推荐|投递邀请|邀请.{0,5}投递", message.subject)
            and not re.search(r"测评|笔试|面试|一面|二面|三面|终面|录用|offer", message.subject, re.IGNORECASE)):
        finish_message(db, message_id, token, "ignored", "职位推荐或投递邀请，未视为已投递岗位的进展")
        return
    try:
        proposal = await analysis.extract(message)
        renew_lease(db, message.account_id, token)
        message.proposal = proposal.model_dump(mode="json", by_alias=True)
        db.commit()
        # 模型等待期间岗位可能已修改，匹配时重新读取完整的阶段与结果记录。
        db.expire_all()
        if proposal.category == "uncertain":
            finish_message(db, message_id, token, "review", proposal.reason)
            return
        if proposal.category != "event" or proposal.event_type == "application_received":
            finish_message(db, message_id, token, "ignored", proposal.reason)
            return
        if not proposal.company or not proposal.company_search_keywords:
            finish_message(db, message_id, token, "review", "公司原名或检索关键词不足，请核对邮件")
            return
        results = [CompanySearchResult.model_validate(execution.search_companies(db, keyword))
                   for keyword in proposal.company_search_keywords]
        proposal.company_search_results = results
        message.proposal = proposal.model_dump(mode="json", by_alias=True)
        db.commit()
        if not any(result.companies for result in results):
            finish_message(db, message_id, token, "review", "各关键词均未找到公司候选，请手动关联")
            return
        renew_lease(db, message.account_id, token)
        names = list(dict.fromkeys(company for result in results for company in result.companies))
        profiles = execution.company_position_context(db, names)
        proposal.company_position_context = profiles
        message.proposal = proposal.model_dump(mode="json", by_alias=True)
        db.commit()
        match = await analysis.match_company(proposal, results, profiles=profiles)
        renew_lease(db, message.account_id, token)
        proposal = proposal.model_copy(update=match.model_dump())
        message.proposal = proposal.model_dump(mode="json", by_alias=True)
        db.commit()
        db.expire_all()
        if not proposal.matched_company:
            finish_message(db, message_id, token, "review", match.company_match_reason)
            return
        candidates = execution.matching_targets(db, proposal)
        if len(candidates) != 1:
            finish_message(db, message_id, token, "review", "未能唯一匹配公司及岗位，请手动关联；岗位简称与同名重投需要核对")
            return
        execution.apply_event(db, message_id, candidates[0], token=token)
    except execution.ReviewRequired as error:
        db.rollback()
        finish_message(db, message_id, token, "review", str(error))
    except HTTPException as error:
        db.rollback()
        finish_message(db, message_id, token, "failed", str(error.detail))
    except Exception:
        db.rollback()
        finish_message(db, message_id, token, "failed", "处理未完成，原邮件已保留，可以重试")


async def run_scan(account_id: int, token: str, *, fetch: bool = True, session_factory=None) -> None:
    factory = session_factory or SessionLocal
    with factory() as db:
        try:
            renew_lease(db, account_id, token)
            account = db.get(MailAccount, account_id)
            if fetch:
                code = await run_in_threadpool(authorization_code, account.address)
                if not code:
                    raise HTTPException(400, "邮箱授权码缺失，请在设置中重新保存")
                batch = await run_in_threadpool(imap_client.read_mailbox, account.address, code,
                                               validity=account.uid_validity, last_uid=account.last_uid)
                store_batch(db, account_id, token, batch)
                upper_uid = batch.get("upper_uid")
                while batch.get("has_more"):
                    batch = await run_in_threadpool(imap_client.read_mailbox, account.address, code,
                        validity=account.uid_validity, last_uid=account.last_uid, through_uid=upper_uid)
                    store_batch(db, account_id, token, batch)
            # 获得新租约后，恢复此前进程中断留下的处理中记录。
            db.execute(update(MailMessage).where(MailMessage.account_id == account_id, MailMessage.status == "analyzing")
                       .values(status="pending", processing_token=None))
            db.commit()
            pending = list(db.scalars(select(MailMessage.id).where(MailMessage.account_id == account_id,
                MailMessage.status == "pending").order_by(MailMessage.id)))
            for message_id in pending:
                await analyze_message(db, message_id, token)
        except HTTPException as error:
            db.rollback()
            db.execute(update(MailAccount).where(MailAccount.id == account_id, MailAccount.scan_token == token)
                       .values(last_error=str(error.detail)[:500]))
            db.commit()
        except Exception:
            db.rollback()
            db.execute(update(MailAccount).where(MailAccount.id == account_id, MailAccount.scan_token == token)
                       .values(last_error="扫描中断，收件游标和已完成记录已保留，可以手动重试"))
            db.commit()
        finally:
            db.execute(update(MailAccount).where(MailAccount.id == account_id, MailAccount.scan_token == token)
                       .values(scan_token=None, lease_until=None))
            db.commit()
