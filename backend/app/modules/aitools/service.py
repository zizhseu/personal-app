"""aitools 模块业务逻辑：LLM 面试官对话 + TTS 语音合成。"""
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TEMPERATURE, TTS_VOICE
from app.modules.qa import service as qa_service


def _interview_system_prompt(db: Session, question_ids: list[int]) -> str:
    """根据选中的八股题目组装面试官人设与题目清单。"""
    questions: list[str] = []
    for qid in question_ids:
        try:
            item = qa_service.get_item(db, qid)
            question = item.question
            if item.answer:
                # 把答案要点给面试官当评判参考（截断防爆 prompt）
                question += f"\n（参考答案要点：{item.answer[:500]}）"
            questions.append(question)
        except HTTPException:
            continue  # 题目已被删，跳过
    q_text = "\n".join(f"{n}. {q}" for n, q in enumerate(questions, 1)) or "（本轮没有可选题目，请自由进行通用面试问答）"

    return f"""你是一位严格但友善的中文技术面试官，正在对候选人进行模拟面试，考察方向是当前题库对应的岗位知识。

本轮面试题目（按顺序提问）：
{q_text}

规则：
1. 一次只问一个问题，等候选人回答。
2. 候选人回答后：先用 1-2 句具体点评（正确/片面/有误，指出遗漏的要点），若回答有明显可深挖的点就追问一个，否则用「下一题：」引出新问题。
3. 全部题目完成后，输出「面试结束」，然后给出整体评价：哪些答得好、哪些需要加强，并建议把薄弱点加入八股复习。
4. 回复保持简洁口语化，每次不超过 200 字。
5. 现在从第 1 题开始，直接提出第一题，不要寒暄。"""


async def llm_chat(messages: list[dict]) -> str:
    """调用 OpenAI 兼容接口（DeepSeek/GLM/任意兼容服务）。"""
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="尚未配置大模型 API Key：请在 backend/.env 中设置 LLM_API_KEY（DeepSeek / 智谱等 OpenAI 兼容服务）后重启",
        )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": LLM_TEMPERATURE,
            },
        )
        if resp.status_code != 200:
            detail = resp.text[:200]
            raise HTTPException(status_code=502, detail=f"大模型服务返回错误（{resp.status_code}）：{detail}")
        return resp.json()["choices"][0]["message"]["content"]


def build_interview_messages(
    system_prompt: str,
    history: list[dict],
    message: str,
) -> list[dict]:
    """system + 截断后的历史 + 最新一条用户消息。"""
    trimmed = history[-20:]
    return [{"role": "system", "content": system_prompt}, *trimmed, {"role": "user", "content": message}]