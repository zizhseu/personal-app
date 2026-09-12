"""qa 模块业务逻辑。"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.qa.models import QaCategory, QaItem
from app.modules.qa.schemas import QaItemCreate, QaItemUpdate


# ---------- 分类 ----------

def list_categories(db: Session) -> list[QaCategory]:
    """分类列表，按创建顺序。"""
    return list(db.scalars(select(QaCategory).order_by(QaCategory.id)).all())


def get_category(db: Session, category_id: int) -> QaCategory:
    row = db.get(QaCategory, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    return row


def _ensure_name_free(db: Session, name: str, exclude_id: int | None = None) -> None:
    stmt = select(QaCategory).where(QaCategory.name == name)
    if exclude_id is not None:
        stmt = stmt.where(QaCategory.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise HTTPException(status_code=400, detail=f"分类「{name}」已存在")


def create_category(db: Session, name: str) -> QaCategory:
    _ensure_name_free(db, name)
    row = QaCategory(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_category(db: Session, category_id: int, name: str) -> QaCategory:
    row = get_category(db, category_id)
    _ensure_name_free(db, name, exclude_id=category_id)
    row.name = name
    db.commit()
    db.refresh(row)
    return row


def delete_category(db: Session, category_id: int) -> None:
    row = get_category(db, category_id)
    count = db.scalar(select(func.count()).select_from(QaItem).where(QaItem.category_id == category_id))
    if count:
        raise HTTPException(
            status_code=400, detail=f"该分类下还有 {count} 道题目，请先删除或移动"
        )
    db.delete(row)
    db.commit()


# ---------- 题目 ----------

def list_items(db: Session, category_id: int | None = None) -> list[QaItem]:
    """全量题目，按创建时间倒序，可按分类过滤。"""
    stmt = select(QaItem).options(joinedload(QaItem.category_rel)).order_by(QaItem.created_at.desc())
    if category_id:
        stmt = stmt.where(QaItem.category_id == category_id)
    return list(db.scalars(stmt).unique().all())


def get_item(db: Session, item_id: int) -> QaItem:
    row = db.get(QaItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return row


def create_item(db: Session, data: QaItemCreate) -> QaItem:
    get_category(db, data.category_id)  # 确认分类存在
    row = QaItem(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_item(db: Session, item_id: int, data: QaItemUpdate) -> QaItem:
    row = get_item(db, item_id)
    updates = data.model_dump(exclude_unset=True)
    if "category_id" in updates:
        get_category(db, updates["category_id"])
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def patch_status(db: Session, item_id: int, status: str) -> QaItem:
    row = get_item(db, item_id)
    row.status = status
    db.commit()
    db.refresh(row)
    return row


def mark_read(db: Session, item_id: int) -> QaItem:
    """进入详情即视为阅读，更新最后阅读时间。"""
    row = get_item(db, item_id)
    row.last_read_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def delete_item(db: Session, item_id: int) -> None:
    row = get_item(db, item_id)
    db.delete(row)
    db.commit()