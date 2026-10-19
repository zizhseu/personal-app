"""本机 OCR；只下载采集结果中的小红书图片，不调用视觉模型或上传图片。"""
from io import BytesIO
from threading import Lock

from fastapi import HTTPException
import httpx

from app.core import config
from app.modules.experiences.collector import image_url

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_engine = None
_lock = Lock()


def available() -> bool:
    from importlib.util import find_spec

    return find_spec("rapidocr") is not None and find_spec("onnxruntime") is not None


def image_path(note_id: int, index: int):
    return config.DATA_DIR / "experience-images" / f"{note_id}-{index}.bin"


async def download(note_id: int, index: int, url: str) -> bytes:
    # 已成功识别的图片由业务状态跳过。重试时重新获取，避免删除资料后
    # SQLite 主键复用而误用旧缓存，也不会把旧图片文字写入另一篇笔记。
    target = image_url(url)
    if not target:
        raise HTTPException(422, "图片地址无效，请打开原笔记核对")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=5), follow_redirects=False) as client:
            for _ in range(3):
                async with client.stream("GET", target, headers={"Referer": "https://www.xiaohongshu.com/"}) as response:
                    if response.is_redirect:
                        target = image_url(str(response.url.join(response.headers.get("location", ""))))
                        if not target:
                            raise HTTPException(422, "图片跳转到不支持的地址")
                        continue
                    if response.status_code != 200:
                        raise HTTPException(502, "图片读取失败，地址可能已过期")
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_IMAGE_BYTES:
                            raise HTTPException(422, "单张图片超过 8 MB，请手动导入需要的文字")
                        chunks.append(chunk)
                    return b"".join(chunks)
        raise HTTPException(502, "图片跳转次数过多，请打开原笔记核对")
    except httpx.RequestError:
        raise HTTPException(502, "图片下载失败，请检查网络后重试") from None


def recognize(data: bytes) -> dict:
    global _engine
    if not available():
        raise HTTPException(503, "本机 OCR 尚未安装，请安装 backend/requirements-experiences.txt 中的依赖")
    try:
        from PIL import Image
        from rapidocr import RapidOCR

        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise HTTPException(422, "图片像素过大，请手动导入需要的文字")
            image.verify()
        with _lock:
            if _engine is None:
                _engine = RapidOCR(params={"EngineConfig.onnxruntime.intra_op_num_threads": 2,
                                           "EngineConfig.onnxruntime.inter_op_num_threads": 1})
            result = _engine(data)
        texts = list(result.txts) if result.txts is not None else []
        scores = [float(score) for score in result.scores] if result.scores is not None else []
        return {"text": "\n".join(texts)[:30000], "confidence": min(scores) if scores else None}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "图片识别失败，请重试或手动补充文字；首次使用需下载 OCR 模型") from None


def store_image(note_id: int, index: int, data: bytes) -> None:
    # 路径完全由数据库主键与图片序号生成，不接受网页或用户提供的文件路径。
    path = image_path(note_id, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
