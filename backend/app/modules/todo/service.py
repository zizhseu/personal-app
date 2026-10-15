"""待办目录与事项增删改查。"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.todo.models import TodoCategory, TodoItem
from app.modules.todo.schemas import TodoItemCreate, TodoItemUpdate


def list_categories(db: Session) -> list[TodoCategory]:
    return list(db.scalars(select(TodoCategory).order_by(TodoCategory.id)).all())


def get_category(db: Session, category_id: int) -> TodoCategory:
    row = db.get(TodoCategory, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="待办目录不存在")
    return row


def save_category(db: Session, name: str, category_id: int | None = None) -> TodoCategory:
    row = get_category(db, category_id) if category_id is not None else TodoCategory()
    row.name = name
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"目录「{name}」已存在") from None
    db.refresh(row)
    return row


def delete_category(db: Session, category_id: int) -> None:
    row = get_category(db, category_id)
    count = db.scalar(select(func.count()).select_from(TodoItem).where(TodoItem.category_id == category_id))
    if count:
        raise HTTPException(status_code=400, detail=f"该目录下还有 {count} 条待办事项，请先删除事项")
    db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="目录下仍有待办事项，无法删除") from None


def list_items(db: Session, category_id: int | None = None) -> list[TodoItem]:
    stmt = select(TodoItem).order_by(TodoItem.id.desc())
    if category_id is not None:
        get_category(db, category_id)
        stmt = stmt.where(TodoItem.category_id == category_id)
    return list(db.scalars(stmt).all())


def get_item(db: Session, item_id: int) -> TodoItem:
    row = db.get(TodoItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    return row


def create_item(db: Session, data: TodoItemCreate) -> TodoItem:
    get_category(db, data.category_id)
    row = TodoItem(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_item(db: Session, item_id: int, data: TodoItemUpdate) -> TodoItem:
    row = get_item(db, item_id)
    updates = data.model_dump(exclude_unset=True)
    completed = updates.pop("completed", row.completed)
    if completed != row.completed:
        row.completed = completed
        row.completed_at = datetime.now() if completed else None
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_item(db: Session, item_id: int) -> None:
    db.delete(get_item(db, item_id))
    db.commit()
