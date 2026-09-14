"""aitools 模块路由：AI 面试对话 + TTS 语音。"""
import edge_tts
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import TTS_VOICE
from app.core.database import get_db
from app.modules.aitools import service
from app.modules.aitools.schemas import InterviewChatRequest, TtsRequest

router = APIRouter(prefix="/api/aitools", tags=["AI 工具"])


@router.get("/status")
def status():
    """前端配置检查：LLM Key 是否已配置。"""
    from app.core.config import LLM_API_KEY

    return {"llmReady": bool(LLM_API_KEY)}


@router.post("/interview/chat")
async def interview_chat(data: InterviewChatRequest, db: Session = Depends(get_db)):
    """AI 面试官对话：根据历史与最新输入生成面试官回复。"""
    system_prompt = service._interview_system_prompt(db, data.questionIds)
    messages = service.build_interview_messages(
        system_prompt,
        [m.model_dump() for m in data.history],
        data.message,
    )
    reply = await service.llm_chat(messages)
    return {"reply": reply}


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