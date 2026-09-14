"""应用配置：单机工具，直接硬编码 + 可选 .env 覆盖。"""
import os
from pathlib import Path

# backend 目录（config.py 位于 backend/app/core/，向上三级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 可选的 backend/.env：KEY=VALUE 逐行，不覆盖已有环境变量
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            import os as _os

            _os.environ.setdefault(_k.strip(), _v.strip())

# SQLite 数据库文件（backend/data/app.db）
DATA_DIR = BASE_DIR / "data"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"

# 开发前端地址（Vite 默认端口）
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ---------- AI 面试：LLM（OpenAI 兼容接口，默认 DeepSeek，可换任意兼容服务） ----------
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# ---------- AI 面试：TTS（edge-tts 神经音色，免费） ----------
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")  # 男声；女声用 zh-CN-XiaoxiaoNeural