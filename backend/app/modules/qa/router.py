"""qa 模块路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.qa import service
from app.modules.qa.schemas import (
    QaCategoryCreate,
    QaCategoryUpdate,
    QaItemCreate,
    QaItemUpdate,
    QaStatusPatch,
)

router = APIRouter(prefix="/api/qa", tags=["面试八股"])


# ---------- 分类 ----------

@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """分类列表（按创建顺序）。"""
    return [c.to_dict() for c in service.list_categories(db)]


@router.post("/categories")
def create_category(data: QaCategoryCreate, db: Session = Depends(get_db)):
    return service.create_category(db, data.name.strip()).to_dict()


@router.put("/categories/{category_id}")
def update_category(category_id: int, data: QaCategoryUpdate, db: Session = Depends(get_db)):
    return service.update_category(db, category_id, data.name.strip()).to_dict()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    service.delete_category(db, category_id)
    return {"ok": True}


# ---------- 题目 ----------

@router.get("/items")
def list_items(category_id: int | None = None, db: Session = Depends(get_db)):
    """全量题目（可按分类过滤）。"""
    return [i.to_dict() for i in service.list_items(db, category_id=category_id)]


@router.post("/items")
def create_item(data: QaItemCreate, db: Session = Depends(get_db)):
    return service.create_item(db, data).to_dict()


@router.put("/items/{item_id}")
def update_item(item_id: int, data: QaItemUpdate, db: Session = Depends(get_db)):
    return service.update_item(db, item_id, data).to_dict()


@router.patch("/items/{item_id}/status")
def patch_status(item_id: int, data: QaStatusPatch, db: Session = Depends(get_db)):
    """切换掌握状态（待复习 / 已掌握）。"""
    return service.patch_status(db, item_id, data.status).to_dict()


@router.patch("/items/{item_id}/read")
def mark_read(item_id: int, db: Session = Depends(get_db)):
    """标记为已阅读（更新最后阅读时间）。"""
    return service.mark_read(db, item_id).to_dict()


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    service.delete_item(db, item_id)
    return {"ok": True}