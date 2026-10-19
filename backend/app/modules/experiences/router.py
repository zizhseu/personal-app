"""面经路由，所有操作限于本机用户。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.experiences import collector, launcher, ocr, service
from threading import Lock
from app.modules.experiences.models import ExperienceNote
from app.modules.experiences.schemas import CollectInput, ExportInput, ManualInput, MaterialInput, SearchInput, WorkInput
from app.modules.settings.router import local_only

router = APIRouter(prefix="/api/experiences", tags=["面经资料"], dependencies=[Depends(local_only)])
_start_lock = Lock()


@router.get("/connection")
def read_connection():
    url, token = collector.connection()
    return {"url": url, "tokenConfigured": bool(token), "ocrReady": ocr.available()}


@router.put("/connection")
def update_connection(payload: dict):
    return collector.save_connection(payload)


@router.get("/connection/start-status")
def startup_status():
    value = launcher.read_status()
    return {"status": value["status"], "message": value["message"]}


@router.post("/connection/start")
def start_collector():
    import os
    import subprocess
    import sys
    from app.core import config

    if os.name != "nt":
        raise HTTPException(400, "一键启动目前支持 Windows，其他系统请自行运行采集服务后配置地址")
    if collector.connection()[0] != "http://127.0.0.1:18060":
        raise HTTPException(400, "自定义服务请自行启动，或先将连接地址恢复为 http://127.0.0.1:18060")
    root = config.BASE_DIR.parent
    with _start_lock:
        state = launcher.read_status()
        if state["status"] == "starting":
            return {"started": True, "message": state["message"]}
        launcher.RUNTIME.mkdir(parents=True, exist_ok=True)
        with (launcher.RUNTIME / "installer.log").open("ab") as output:
            process = subprocess.Popen([sys.executable, str(root / "scripts" / "xhs_collector.py"), "start", "--data-dir", str(config.DATA_DIR)],
                cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)
        extra = {"pid": state["pid"]} if state.get("pid") else {}
        launcher.write_status("starting", "正在准备本机采集组件…", workerPid=process.pid, **extra)
    return {"started": True, "message": "已开始准备采集服务，可稍后检查登录；首次启动需要联网下载组件和浏览器"}


@router.get("/login")
async def login_status():
    data = await collector.call("GET", "/api/v1/login/status")
    return {"loggedIn": data.get("is_logged_in") is True}


@router.post("/login/qrcode")
async def login_qrcode():
    data = await collector.call("GET", "/api/v1/login/qrcode")
    image = data.get("img", "")
    if image and (not isinstance(image, str) or not image.startswith("data:image/png;base64,") or len(image) > 2_000_000):
        raise HTTPException(502, "采集服务返回的登录二维码不兼容")
    return {"loggedIn": data.get("is_logged_in") is True, "image": image, "timeout": str(data.get("timeout", "300"))[:10]}


@router.post("/search")
async def search(data: SearchInput, db: Session = Depends(get_db)):
    if not data.keyword.strip():
        raise HTTPException(422, "请输入搜索关键词")
    result = await collector.search(data.keyword, data.sort, data.period)
    saved = {note.source_id: note.id for note in db.scalars(select(ExperienceNote).where(ExperienceNote.platform == "xiaohongshu"))}
    for item in result["items"]:
        item["savedId"] = saved.get(item["sourceId"])
    return result


@router.post("/collect")
async def collect(data: CollectInput, db: Session = Depends(get_db)):
    return await service.collect(db, data.result_id)


@router.post("/manual")
def manual(data: ManualInput, db: Session = Depends(get_db)):
    return service.manual(db, data)


@router.get("/notes")
def notes(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(ExperienceNote).order_by(ExperienceNote.updated_at.desc())))
    return [service.get_note(db, row.id).to_dict(detail=False) for row in rows]


@router.get("/notes/{note_id}")
def read_note(note_id: int, db: Session = Depends(get_db)):
    return service.detail(db, note_id)


@router.put("/notes/{note_id}/material")
def edit_material(note_id: int, data: MaterialInput, db: Session = Depends(get_db)):
    return service.edit_material(db, note_id, data)


@router.post("/notes/{note_id}/ocr")
async def recognize_images(note_id: int, data: WorkInput, db: Session = Depends(get_db)):
    return await service.recognize_images(db, note_id, str(data.request_id))


@router.post("/notes/{note_id}/analyze")
async def analyze(note_id: int, data: WorkInput, db: Session = Depends(get_db)):
    return await service.analyze(db, note_id, str(data.request_id))


@router.post("/notes/{note_id}/export")
def export(note_id: int, data: ExportInput, db: Session = Depends(get_db)):
    return service.export_question(db, note_id, data)


@router.get("/notes/{note_id}/images/{index}")
def read_image(note_id: int, index: int, db: Session = Depends(get_db)):
    row = service.get_note(db, note_id)
    if not 0 <= index < len(row.images) or not row.images[index].get("stored") or not ocr.image_path(note_id, index).exists():
        raise HTTPException(404, "本机尚未保存此图片，请先识别图片")
    from PIL import Image

    with Image.open(ocr.image_path(note_id, index)) as image:
        media_type = Image.MIME.get(image.format, "application/octet-stream")
    return FileResponse(ocr.image_path(note_id, index), media_type=media_type, headers={"Cache-Control": "no-store"})


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    row = service.get_note(db, note_id)
    if row.work_status == "pending":
        raise HTTPException(409, "资料正在处理，请稍后删除")
    indexes = range(len(row.images))
    db.delete(row)
    db.commit()
    for index in indexes:
        try:
            ocr.image_path(note_id, index).unlink(missing_ok=True)
        except OSError:
            # Windows 图片仍被读取时保留缓存，不让已完成的数据库删除回报失败。
            pass
    return {"ok": True}
