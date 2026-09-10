"""应用配置：单机工具，直接硬编码。"""
from pathlib import Path

# backend 目录（config.py 位于 backend/app/core/，向上三级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SQLite 数据库文件（backend/data/app.db）
DATA_DIR = BASE_DIR / "data"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"

# 开发前端地址（Vite 默认端口）
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]