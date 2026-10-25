"""代码手撕分类与题目接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.coding import service
from app.modules.coding.models import CodingCategory
from app.modules.coding.schemas import CategoryInput, ItemInput, StatusInput

router = APIRouter(prefix="/api/coding", tags=["代码手撕"])


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [row.to_dict() for row in db.scalars(select(CodingCategory).order_by(CodingCategory.id))]


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
def items(category_id: int | None = None, db: Session = Depends(get_db)):
    return [row.to_dict(detail=False) for row in service.list_items(db, category_id)]


@router.post("/items")
def create_item(data: ItemInput, db: Session = Depends(get_db)):
    return service.save_item(db, data).to_dict()


@router.get("/items/{item_id}")
def read_item(item_id: int, db: Session = Depends(get_db)):
    return service.get_item(db, item_id).to_dict()


@router.put("/items/{item_id}")
def update_item(item_id: int, data: ItemInput, db: Session = Depends(get_db)):
    return service.save_item(db, data, item_id).to_dict()


@router.patch("/items/{item_id}/status")
def patch_status(item_id: int, data: StatusInput, db: Session = Depends(get_db)):
    row = service.get_item(db, item_id)
    row.status = data.status
    db.commit()
    return row.to_dict()


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db.delete(service.get_item(db, item_id))
    db.commit()
    return {"ok": True}
