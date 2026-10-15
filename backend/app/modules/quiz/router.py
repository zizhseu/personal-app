"""quiz 模块路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.quiz import service
from app.modules.quiz.schemas import (
    QuizCategoryCreate,
    QuizCategoryUpdate,
    QuizItemCreate,
    QuizItemUpdate,
    QuizParseRequest,
)

router = APIRouter(prefix="/api/quiz", tags=["笔试选择"])


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [c.to_dict() for c in service.list_categories(db)]


@router.post("/categories")
def create_category(data: QuizCategoryCreate, db: Session = Depends(get_db)):
    return service.create_category(db, data.name).to_dict()


@router.put("/categories/{category_id}")
def update_category(category_id: int, data: QuizCategoryUpdate, db: Session = Depends(get_db)):
    return service.update_category(db, category_id, data.name).to_dict()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    service.delete_category(db, category_id)
    return {"ok": True}


@router.get("/items")
def list_items(category_id: int | None = None, db: Session = Depends(get_db)):
    return [i.to_dict() for i in service.list_items(db, category_id=category_id)]


@router.post("/items")
def create_item(data: QuizItemCreate, db: Session = Depends(get_db)):
    return service.create_item(db, data).to_dict()


@router.put("/items/{item_id}")
def update_item(item_id: int, data: QuizItemUpdate, db: Session = Depends(get_db)):
    return service.update_item(db, item_id, data).to_dict()


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    service.delete_item(db, item_id)
    return {"ok": True}


@router.post("/parse")
async def parse_quiz(data: QuizParseRequest, db: Session = Depends(get_db)):
    """AI 解析导入：把原始文本解析为选择题候选列表（不入库，前端预览确认）。"""
    questions = await service.parse_quiz_text(data.text)
    return {"questions": questions}