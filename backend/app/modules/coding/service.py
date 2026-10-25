"""分类和手撕题的保存规则。"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from app.modules.coding.models import CodingCategory, CodingItem
from app.modules.coding.schemas import ItemInput


def get_category(db: Session, category_id: int):
    row = db.get(CodingCategory, category_id)
    if row is None:
        raise HTTPException(404, "手撕题分类不存在")
    return row


def save_category(db: Session, name: str, category_id: int | None = None):
    row = get_category(db, category_id) if category_id is not None else CodingCategory()
    row.name = name
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "已存在同名分类") from None
    return row


def delete_category(db: Session, category_id: int):
    row = get_category(db, category_id)
    if db.scalar(select(CodingItem.id).where(CodingItem.category_id == category_id).limit(1)) is not None:
        raise HTTPException(400, "分类下仍有手撕题，请先移动或删除题目")
    db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "分类下仍有手撕题，请刷新后重试") from None


def get_item(db: Session, item_id: int):
    row = db.get(CodingItem, item_id)
    if row is None:
        raise HTTPException(404, "手撕题不存在")
    return row


def list_items(db: Session, category_id: int | None):
    # 列表不加载整段代码和长文本，打开详情时再读取。
    query = select(CodingItem).options(defer(CodingItem.code), defer(CodingItem.description),
        defer(CodingItem.approach), defer(CodingItem.complexity)).order_by(CodingItem.updated_at.desc(), CodingItem.id.desc())
    if category_id is not None:
        query = query.where(CodingItem.category_id == category_id)
    return list(db.scalars(query))


def save_item(db: Session, data: ItemInput, item_id: int | None = None):
    row = get_item(db, item_id) if item_id is not None else CodingItem()
    get_category(db, data.category_id)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "分类已变化，请刷新后重试") from None
    return row
