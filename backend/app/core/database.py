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
        if "offer_decision" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN offer_decision VARCHAR(20)"))
            conn.commit()
        if "base" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN base JSON"))
            conn.commit()

        # 地点字段已并入 Base：老数据的 location 按分隔符拆分迁入 base（仅处理 base 为空的行）
        import json as _json
        import re as _re

        rows = conn.execute(
            text(
                "SELECT id, location FROM application "
                "WHERE base IS NULL AND location IS NOT NULL AND TRIM(location) != ''"
            )
        ).all()
        for rid, loc in rows:
            cities = [c.strip() for c in _re.split(r"[/、,，;；\s]+", loc) if c.strip()]
            if cities:
                conn.execute(
                    text("UPDATE application SET base = :b WHERE id = :id"),
                    {"b": _json.dumps(cities, ensure_ascii=False), "id": rid},
                )
        conn.commit()

        # qa_item 补列（表已存在的老库；全新库由 create_all 直接带上）
        qa_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(qa_item)"))]
        if qa_cols and "tags" not in qa_cols:
            conn.execute(text("ALTER TABLE qa_item ADD COLUMN tags JSON"))
            conn.commit()
        if qa_cols and "last_read_at" not in qa_cols:
            conn.execute(text("ALTER TABLE qa_item ADD COLUMN last_read_at DATETIME"))
            conn.commit()

        # 分类实体化迁移：qa_item 补 category_id 列 + 初始化内置分类 + 按旧字符串回填
        if qa_cols and "category_id" not in qa_cols:
            conn.execute(text("ALTER TABLE qa_item ADD COLUMN category_id INTEGER"))
            conn.commit()
        if conn.execute(text("SELECT COUNT(*) FROM qa_category")).scalar() == 0:
            for name in ("简历项目", "后端/中间件", "Agent"):
                conn.execute(text("INSERT INTO qa_category (name) VALUES (:name)"), {"name": name})
            conn.commit()
        # 旧 category 字符串（resume/backend/agent）→ 分类 id 一次性回填
        if qa_cols and "category" in qa_cols:
            name_map = {"resume": "简历项目", "backend": "后端/中间件", "agent": "Agent"}
            for old_name, cname in name_map.items():
                conn.execute(
                    text(
                        "UPDATE qa_item SET category_id = "
                        "(SELECT id FROM qa_category WHERE name = :cname) "
                        "WHERE category = :oname AND category_id IS NULL"
                    ),
                    {"cname": cname, "oname": old_name},
                )
            conn.commit()

        # 旧 qa_item 的 category 列为 NOT NULL 且已废弃 → 重建表移除该列/约束
        if qa_cols and "category" in qa_cols:
            conn.execute(text("DROP TABLE IF EXISTS qa_item_new"))
            conn.execute(
                text(
                    """
                    CREATE TABLE qa_item_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_id INTEGER NOT NULL REFERENCES qa_category(id),
                        question VARCHAR(500) NOT NULL,
                        answer TEXT,
                        tags JSON,
                        status VARCHAR(20) NOT NULL,
                        last_read_at DATETIME,
                        created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                        updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO qa_item_new (id, category_id, question, answer, tags, status, last_read_at, created_at, updated_at)
                    SELECT id,
                           COALESCE(category_id, (SELECT MIN(id) FROM qa_category)),
                           question, answer, tags, status, last_read_at, created_at, updated_at
                    FROM qa_item
                    """
                )
            )
            conn.execute(text("DROP TABLE qa_item"))
            conn.execute(text("ALTER TABLE qa_item_new RENAME TO qa_item"))
            conn.execute(text("CREATE INDEX ix_qa_item_category_id ON qa_item (category_id)"))
            conn.commit()

        # 状态合并迁移：applied/viewed → screening（投递表与状态历史同步）
        conn.execute(
            text(
                "UPDATE application SET status = 'screening' "
                "WHERE status IN ('applied', 'viewed')"
            )
        )
        conn.execute(
            text(
                "UPDATE status_history SET status = 'screening' "
                "WHERE status IN ('applied', 'viewed')"
            )
        )
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

        # 轮次结果枚举细化：老「待定」按截止时间是否已过 → 已完成 / 未开始
        from datetime import datetime

        now_local = datetime.now().isoformat(sep=" ")
        conn.execute(
            text(
                "UPDATE interview_round SET result = 'completed' "
                "WHERE result = 'pending' AND scheduled_at IS NOT NULL AND scheduled_at < :now"
            ),
            {"now": now_local},
        )
        conn.execute(text("UPDATE interview_round SET result = 'not_started' WHERE result = 'pending'"))
        conn.commit()