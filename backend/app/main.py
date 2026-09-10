"""应用入口：CORS → 模块注册 → 建表（时序不可颠倒）。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.core.database import init_db
from app.core.module_registry import AppModule, register_modules

loaded_modules: list[str] = []


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 模块已在导入期注册（见下），这里启动时建表
    init_db()
    yield


app = FastAPI(title="个人 App", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 先注册模块（导入过程会把各模块模型注册进 Base.metadata），lifespan 里再建表
loaded_modules = register_modules(app)


@app.get("/api/health", tags=["系统"])
def health() -> dict:
    """健康检查，兼当模块注册自检。"""
    return {"status": "ok", "modules": loaded_modules}