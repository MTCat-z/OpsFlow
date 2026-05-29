from sqlmodel import SQLModel, create_engine, Session, text
from app.core.config import settings

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)


def _migrate_columns():
    """为已有表自动补充缺失列（SQLite create_all 不会 ALTER TABLE）"""
    _MIGRATIONS = {
        'assets': [
            ('ssh_private_key_encrypted', 'VARCHAR'),
            ('auth_type', "VARCHAR(20) DEFAULT 'password'"),
        ],
        'broadband_contracts': [
            ('renewal_cycle', "VARCHAR(20) DEFAULT 'annual'"),
            ('renewal_cost', 'FLOAT'),
        ],
    }
    with engine.connect() as conn:
        for table, columns in _MIGRATIONS.items():
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in result}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    print(f"[migration] Added {table}.{col_name}")
        conn.commit()


def create_db_and_tables():
    from app.models import asset, scan_task, iperf_task, broadband, topology, user  # noqa: F401
    SQLModel.metadata.create_all(engine)
    if "sqlite" in settings.DATABASE_URL:
        _migrate_columns()


def get_session():
    with Session(engine) as session:
        yield session
