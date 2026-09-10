"""数据库基建：engine、会话、建表。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATA_DIR, DATABASE_URL

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# SQLite 默认不启用外键约束，必须显式开启，否则 ON DELETE CASCADE 不生效
@listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _):  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表 + 轻量迁移。必须在 register_modules() 之后调用，模块导入时模型才注册进 metadata。"""
    from sqlalchemy import text

    from app.shared.base import Base

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)

    # 老库补列（create_all 不会给已有表加列；ALTER 幂等：列已存在则跳过）
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(application)"))]
        if "url" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN url VARCHAR(500)"))
            conn.commit()
        if "reject_stage" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN reject_stage VARCHAR(20)"))
            conn.commit()

        round_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(interview_round)"))]
        if "start_at" not in round_cols:
            conn.execute(text("ALTER TABLE interview_round ADD COLUMN start_at DATETIME"))
            conn.execute(text("ALTER TABLE interview_round ADD COLUMN duration_minutes INTEGER"))
            # 老数据「计划时间」视为开始时间（持续时间为空 → 截止 = 开始，展示不变）
            conn.execute(
                text(
                    "UPDATE interview_round SET start_at = scheduled_at "
                    "WHERE start_at IS NULL AND scheduled_at IS NOT NULL"
                )
            )
            conn.commit()

        # 状态历史：为没有历史记录的投递补一条初始状态（时间取投递创建时间），幂等
        conn.execute(
            text(
                "INSERT INTO status_history (application_id, status, changed_at, created_at, updated_at) "
                "SELECT id, status, created_at, created_at, created_at FROM application "
                "WHERE id NOT IN (SELECT application_id FROM status_history)"
            )
        )
        conn.commit()