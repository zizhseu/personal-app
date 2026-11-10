"""邮箱设置与处理记录接口，后台按小时调度。"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.modules.settings.router import local_only

from . import execution, service
from .models import MailAccount, MailMessage
from .schemas import ApplyMessage, MailSettings

logger = logging.getLogger(__name__)


async def scheduler():
    while True:
        try:
            with SessionLocal() as db:
                account = service.current_account(db)
                if account and account.enabled and account.next_scan_at <= datetime.now():
                    account_id = account.id
                    try:
                        token = service.claim_scan(db, account_id, scheduled=True)
                    except HTTPException:
                        token = None
                else:
                    token = None
            if token:
                await service.run_scan(account_id, token)
        except Exception:
            # 不将邮件内容、地址或授权信息写入运行日志。
            logger.warning("邮箱定时任务暂未完成，将在下一轮检查恢复")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_):
    task = asyncio.create_task(scheduler())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


router = APIRouter(prefix="/api/mailbox", tags=["邮箱同步"], lifespan=lifespan)


def parse_settings(payload: dict) -> MailSettings:
    try:
        return MailSettings.model_validate(payload)
    except ValidationError:
        raise HTTPException(400, "请填写有效的 163 邮箱地址及客户端授权码") from None


@router.get("/settings", dependencies=[Depends(local_only)])
def settings(db: Session = Depends(get_db)):
    return service.public_settings(db)


@router.put("/settings", dependencies=[Depends(local_only)])
async def save_settings(payload: dict, db: Session = Depends(get_db)):
    return await service.save_settings(db, parse_settings(payload))


@router.post("/settings/test", dependencies=[Depends(local_only)])
async def test_settings(payload: dict):
    await service.test_connection(parse_settings(payload))
    return {"ok": True}


@router.get("/status")
def status(db: Session = Depends(get_db)):
    account = service.current_account(db)
    return {"account": account.to_dict() if account else None, "intervalMinutes": 60}


@router.post("/scan", status_code=202)
def scan(tasks: BackgroundTasks, db: Session = Depends(get_db)):
    account = service.current_account(db)
    if account is None:
        raise HTTPException(400, "请先在设置中连接 163 邮箱")
    token = service.claim_scan(db, account.id)
    tasks.add_task(service.run_scan, account.id, token)
    return {"accepted": True}


@router.get("/messages")
def messages(status: str | None = None, page: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    account = service.current_account(db)
    if account is None:
        return {"items": [], "total": 0, "counts": {}}
    base = select(MailMessage).where(MailMessage.account_id == account.id)
    if status:
        base = base.where(MailMessage.status == status)
    count = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(MailMessage.id.desc()).offset((page - 1) * 30).limit(30))
    counts = dict(db.execute(select(MailMessage.status, func.count()).where(MailMessage.account_id == account.id)
                            .group_by(MailMessage.status)).all())
    return {"items": [row.to_dict() for row in rows], "total": count, "counts": counts}


@router.get("/targets")
def targets(db: Session = Depends(get_db)):
    return execution.targets(db)


@router.get("/company-targets")
def company_targets(db: Session = Depends(get_db)):
    return execution.company_targets(db)


@router.get("/companies/search")
def search_companies(keyword: str = Query(min_length=1, max_length=40), db: Session = Depends(get_db)):
    return execution.search_companies(db, keyword)


@router.get("/messages/{message_id}")
def message_detail(message_id: int, db: Session = Depends(get_db)):
    message = db.get(MailMessage, message_id)
    if message is None:
        raise HTTPException(404, "邮件记录不存在")
    return message.to_dict(detail=True)


@router.post("/messages/{message_id}/apply")
def apply_message(message_id: int, data: ApplyMessage, db: Session = Depends(get_db)):
    target = {"applicationId": data.application_id, "positionVersion": data.position_version,
              "position": data.position, "expectedUpdatedAt": data.expected_updated_at.isoformat(),
              "expectedSnapshot": data.expected_snapshot}
    if data.new_position:
        target.update(createPosition=True, newPosition=data.new_position,
                      expectedCompanySnapshot=data.expected_company_snapshot)
    try:
        return execution.apply_event(db, message_id, target, manual=True, selected_round_id=data.round_id).to_dict(detail=True)
    except execution.ReviewRequired as error:
        db.rollback()
        raise HTTPException(409, str(error)) from None


@router.post("/messages/{message_id}/retry", status_code=202)
def retry_message(message_id: int, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    message = db.get(MailMessage, message_id)
    account = service.current_account(db)
    if message is None or account is None or message.account_id != account.id:
        raise HTTPException(404, "当前邮箱的邮件记录不存在")
    if message.status in ("applied", "unchanged", "analyzing", "pending"):
        raise HTTPException(409, "该邮件已更新或正在处理，请刷新记录")
    token = service.claim_scan(db, account.id)
    db.refresh(message)
    if message.status in ("applied", "unchanged", "analyzing", "pending"):
        db.execute(update(MailAccount).where(MailAccount.id == account.id, MailAccount.scan_token == token)
                   .values(scan_token=None, lease_until=None))
        db.commit()
        raise HTTPException(409, "邮件处理状态已变化，请刷新后重试")
    message.status, message.reason = "pending", None
    db.commit()
    tasks.add_task(service.run_scan, account.id, token, fetch=False)
    return {"accepted": True}


@router.post("/messages/{message_id}/ignore")
def ignore_message(message_id: int, db: Session = Depends(get_db)):
    message = db.get(MailMessage, message_id)
    if message is None:
        raise HTTPException(404, "邮件记录不存在")
    changed = db.execute(update(MailMessage).where(MailMessage.id == message_id,
        MailMessage.status.in_(("review", "failed"))).values(status="ignored", reason="用户已核对并忽略"))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "仅待核对或失败的邮件可以忽略")
    db.commit()
    return message.to_dict(detail=True)
