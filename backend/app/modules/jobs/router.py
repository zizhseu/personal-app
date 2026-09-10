"""jobs 模块路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.jobs import service
from app.modules.jobs.schemas import (
    ApplicationCreate,
    ApplicationStatusPatch,
    ApplicationUpdate,
    EventCreate,
    EventUpdate,
    RoundCreate,
    RoundUpdate,
)

router = APIRouter(prefix="/api/jobs", tags=["秋招投递"])


@router.get("/applications")
def list_applications(
    status: str | None = None,
    channel: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
):
    """全量投递列表（含轮次），支持状态/渠道/关键字筛选。"""
    rows = service.list_applications(db, status=status, channel=channel, keyword=keyword)
    return [r.to_dict() for r in rows]


@router.post("/applications")
def create_application(data: ApplicationCreate, db: Session = Depends(get_db)):
    return service.create_application(db, data).to_dict()


@router.get("/applications/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    return service.get_application(db, app_id).to_dict()


@router.put("/applications/{app_id}")
def update_application(app_id: int, data: ApplicationUpdate, db: Session = Depends(get_db)):
    return service.update_application(db, app_id, data).to_dict()


@router.patch("/applications/{app_id}/status")
def patch_status(app_id: int, data: ApplicationStatusPatch, db: Session = Depends(get_db)):
    return service.patch_status(db, app_id, data).to_dict()


@router.delete("/applications/{app_id}")
def delete_application(app_id: int, db: Session = Depends(get_db)):
    service.delete_application(db, app_id)
    return {"ok": True}


@router.post("/applications/{app_id}/rounds")
def create_round(app_id: int, data: RoundCreate, db: Session = Depends(get_db)):
    return service.create_round(db, app_id, data).to_dict()


@router.put("/rounds/{round_id}")
def update_round(round_id: int, data: RoundUpdate, db: Session = Depends(get_db)):
    return service.update_round(db, round_id, data).to_dict()


@router.delete("/rounds/{round_id}")
def delete_round(round_id: int, db: Session = Depends(get_db)):
    service.delete_round(db, round_id)
    return {"ok": True}


@router.get("/events")
def list_events(db: Session = Depends(get_db)):
    """全量自定义日程，按时间升序。"""
    return [e.to_dict() for e in service.list_events(db)]


@router.post("/events")
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    return service.create_event(db, data).to_dict()


@router.put("/events/{event_id}")
def update_event(event_id: int, data: EventUpdate, db: Session = Depends(get_db)):
    return service.update_event(db, event_id, data).to_dict()


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    service.delete_event(db, event_id)
    return {"ok": True}