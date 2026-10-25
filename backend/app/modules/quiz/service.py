"""quiz 模块业务逻辑：分类 / 题目 / AI 解析导入。"""
import re

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.aitools.service import llm_chat
from app.modules.quiz.models import QuizCategory, QuizItem
from app.modules.quiz.schemas import QuizItemCreate, QuizItemUpdate, QuizParseResult, validate_answer_indices


# ---------- 分类 ----------

def list_categories(db: Session) -> list[QuizCategory]:
    return list(db.scalars(select(QuizCategory).order_by(QuizCategory.id)).all())


def get_category(db: Session, category_id: int) -> QuizCategory:
    row = db.get(QuizCategory, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    return row


def _ensure_name_free(db: Session, name: str, exclude_id: int | None = None) -> None:
    stmt = select(QuizCategory).where(QuizCategory.name == name)
    if exclude_id is not None:
        stmt = stmt.where(QuizCategory.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise HTTPException(status_code=400, detail=f"分类「{name}」已存在")


def create_category(db: Session, name: str) -> QuizCategory:
    _ensure_name_free(db, name)
    row = QuizCategory(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_category(db: Session, category_id: int, name: str) -> QuizCategory:
    row = get_category(db, category_id)
    _ensure_name_free(db, name, exclude_id=category_id)
    row.name = name
    db.commit()
    db.refresh(row)
    return row


def delete_category(db: Session, category_id: int) -> None:
    row = get_category(db, category_id)
    count = db.scalar(select(func.count()).select_from(QuizItem).where(QuizItem.category_id == category_id))
    if count:
        raise HTTPException(status_code=400, detail=f"该分类下还有 {count} 道题目，请先删除或移动")
    db.delete(row)
    db.commit()


# ---------- 题目 ----------

def list_items(db: Session, category_id: int | None = None) -> list[QuizItem]:
    """全量题目，按创建顺序，可按分类过滤。"""
    stmt = select(QuizItem).options(joinedload(QuizItem.category_rel)).order_by(QuizItem.id)
    if category_id:
        stmt = stmt.where(QuizItem.category_id == category_id)
    return list(db.scalars(stmt).unique().all())


def get_item(db: Session, item_id: int) -> QuizItem:
    row = db.get(QuizItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return row


def _validate_answer(answer: list[int], options_count: int, qtype: str) -> list[int]:
    """将共享答案约束转换为编辑接口的参数错误。"""
    try:
        return validate_answer_indices(answer, options_count, qtype)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def create_item(db: Session, data: QuizItemCreate) -> QuizItem:
    get_category(db, data.category_id)  # 确认分类存在
    answer = _validate_answer(list(data.answer), len(data.options), data.qtype)
    row = QuizItem(
        category_id=data.category_id,
        question=data.question,
        options=data.options,
        answer=answer,
        qtype=data.qtype,
        analysis=data.analysis,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_item(db: Session, item_id: int, data: QuizItemUpdate) -> QuizItem:
    row = get_item(db, item_id)
    updates = data.model_dump(exclude_unset=True)
    if "category_id" in updates:
        get_category(db, updates["category_id"])
    if "options" in updates or "answer" in updates or "qtype" in updates:
        options = updates.get("options", row.options)
        qtype = updates.get("qtype", row.qtype)
        answer = updates.get("answer", row.answer)
        updates["answer"] = _validate_answer(list(answer), len(options), qtype)
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_item(db: Session, item_id: int) -> None:
    row = get_item(db, item_id)
    db.delete(row)
    db.commit()


# ---------- AI 解析导入 ----------

_PARSE_PROMPT = """从下面的文本中提取所有选择题（笔试题目），输出 JSON。

输出格式（只输出 JSON，不要其他内容）：
{"questions": [{"question": "题干", "options": ["选项文本", ...], "answer": [0], "qtype": "single", "analysis": "解析"}]}

要求：
1. options 只保留选项文字本身（去掉 A.、B.、（A）等前缀），按原文顺序。
2. answer 是正确选项的下标数组（从 0 开始）；单选恰好 1 个，多选至少 2 个，不能越界。
3. qtype：只有一个正确答案为 "single"，多个正确答案为 "multi"；无法判断时按 single。
4. analysis 为该题的解析说明，原文没有则用空字符串。
5. 题干不完整或不是选择题的直接跳过。
6. 文本中没有选择题时返回 {"questions": []}。
7. 每道题须有 2 到 8 个非空选项，不能猜测或补造原文未提供的正确答案。

文本：
"""


async def parse_quiz_text(text: str) -> list[dict]:
    """调用 LLM 从原始文本解析选择题候选列表（不入库，由前端预览确认）。"""
    content = await llm_chat([{"role": "user", "content": _PARSE_PROMPT + text}])
    # 剥离可能的 ```json 包裹
    cleaned = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    try:
        parsed = QuizParseResult.model_validate_json(cleaned)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="AI 返回的题目格式不符合要求，请检查原文后重新解析") from exc
    if not parsed.questions:
        raise HTTPException(status_code=422, detail="未能从文本中解析出选择题，请检查文本内容")
    return [
        {**question.model_dump(), "analysis": question.analysis or ""}
        for question in parsed.questions
    ]
