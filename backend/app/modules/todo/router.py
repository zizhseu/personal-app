"""待办目录与事项接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.todo import service
from app.modules.todo.schemas import CategoryInput, TodoItemCreate, TodoItemUpdate

router = APIRouter(prefix="/api/todo", tags=["待办事项"])


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [row.to_dict() for row in service.list_categories(db)]


@router.post("/categories")
def create_category(data: CategoryInput, db: Session = Depends(get_db)):
    return service.save_category(db, data.name).to_dict()


@router.put("/categories/{category_id}")
def rename_category(category_id: int, data: CategoryInput, db: Session = Depends(get_db)):
    return service.save_category(db, data.name, category_id).to_dict()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    service.delete_category(db, category_id)
    return {"ok": True}


@router.get("/items")
def list_items(category_id: int | None = None, db: Session = Depends(get_db)):
    return [row.to_dict() for row in service.list_items(db, category_id)]


@router.post("/items")
def create_item(data: TodoItemCreate, db: Session = Depends(get_db)):
    return service.create_item(db, data).to_dict()


@router.put("/items/{item_id}")
def update_item(item_id: int, data: TodoItemUpdate, db: Session = Depends(get_db)):
    return service.update_item(db, item_id, data).to_dict()


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    service.delete_item(db, item_id)
    return {"ok": True}
