"""简历材料、面试记录、复盘与语音接口。"""
import edge_tts
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import TTS_VOICE
from app.core.database import get_db
from app.modules.aitools import interviews
from app.modules.aitools.documents import MAX_UPLOAD_BYTES, extract_resume
from app.modules.aitools.models import InterviewOperation, InterviewSession, ResumeDocument
from app.modules.aitools.schemas import AnswerRequest, InterviewCreate, OperationRequest, ResumeInput, ReviewActionInput, TtsRequest

router = APIRouter(prefix="/api/aitools", tags=["AI 工具"])


@router.get("/status")
def status():
    """前端配置检查：LLM Key 是否已配置。"""
    from app.core.config import LLM_API_KEY

    return {"llmReady": bool(LLM_API_KEY)}


@router.get("/resumes")
def list_resumes(db: Session = Depends(get_db)):
    return [row.to_dict(include_content=False) for row in db.scalars(select(ResumeDocument).order_by(ResumeDocument.updated_at.desc()))]


@router.post("/resumes/extract")
async def extract_resume_file(file: UploadFile = File(...)):
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        return await run_in_threadpool(extract_resume, file.filename or "", content)
    finally:
        await file.close()


@router.post("/resumes")
def create_resume(data: ResumeInput, db: Session = Depends(get_db)):
    return interviews.save_resume(db, data).to_dict()


@router.get("/resumes/{resume_id}")
def read_resume(resume_id: int, db: Session = Depends(get_db)):
    return interviews.get_resume(db, resume_id).to_dict()


@router.put("/resumes/{resume_id}")
def update_resume(resume_id: int, data: ResumeInput, db: Session = Depends(get_db)):
    return interviews.save_resume(db, data, resume_id).to_dict()


@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    db.delete(interviews.get_resume(db, resume_id))
    db.commit()
    return {"ok": True}


@router.get("/interviews")
def list_interviews(db: Session = Depends(get_db)):
    return [row.to_dict() for row in db.scalars(select(InterviewSession).order_by(InterviewSession.updated_at.desc()))]


@router.post("/interviews")
def create_interview(data: InterviewCreate, db: Session = Depends(get_db)):
    return interviews.create_session(db, data)


@router.get("/interviews/{session_id}")
def read_interview(session_id: int, db: Session = Depends(get_db)):
    return interviews.session_detail(db, session_id)


@router.delete("/interviews/{session_id}")
def delete_interview(session_id: int, db: Session = Depends(get_db)):
    db.delete(interviews.get_session(db, session_id))
    db.commit()
    return {"ok": True}


@router.post("/interviews/{session_id}/start")
async def start_interview(session_id: int, data: OperationRequest, db: Session = Depends(get_db)):
    return await interviews.generate(db, session_id, "start", str(data.request_id))


@router.post("/interviews/{session_id}/messages")
async def answer_interview(session_id: int, data: AnswerRequest, db: Session = Depends(get_db)):
    return await interviews.generate(db, session_id, "reply", str(data.request_id), data.content)


@router.post("/interviews/{session_id}/review")
async def review_interview(session_id: int, data: OperationRequest, db: Session = Depends(get_db)):
    return await interviews.generate(db, session_id, "review", str(data.request_id))


@router.post("/interviews/{session_id}/retry")
async def retry_interview(session_id: int, data: OperationRequest, db: Session = Depends(get_db)):
    operation = db.get(InterviewOperation, str(data.request_id))
    if operation is None or operation.session_id != session_id:
        raise HTTPException(404, "待重试的请求不存在")
    return await interviews.generate(db, session_id, operation.kind, operation.id, retry=True)


@router.post("/interviews/{session_id}/actions")
def export_review(session_id: int, data: ReviewActionInput, db: Session = Depends(get_db)):
    return interviews.export_review_item(db, session_id, data)


@router.post("/tts")
async def tts(data: TtsRequest):
    """文本转语音（edge-tts 神经音色），返回 mp3 音频流。"""
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    async def audio_stream():
        com = edge_tts.Communicate(text[:600], TTS_VOICE)
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(audio_stream(), media_type="audio/mpeg")
