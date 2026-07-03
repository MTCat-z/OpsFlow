from sqlmodel import SQLModel, create_engine, Session, text
from app.core.config import settings

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False, "timeout": 30}

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


def _ensure_indexes():
    """为已有数据库补充索引（CREATE INDEX IF NOT EXISTS）"""
    _INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_assets_ip ON assets(ip_address)",
        "CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)",
        "CREATE INDEX IF NOT EXISTS idx_inspection_runs_plan ON inspection_runs(plan_id)",
        "CREATE INDEX IF NOT EXISTS idx_inspection_runs_status ON inspection_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_inspection_runs_created ON inspection_runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_config_snapshots_job ON config_snapshots(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_config_snapshots_asset ON config_snapshots(asset_id)",
        "CREATE INDEX IF NOT EXISTS idx_config_snapshots_created ON config_snapshots(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_config_snapshots_hash ON config_snapshots(content_hash)",
        "CREATE INDEX IF NOT EXISTS idx_command_results_batch ON command_results(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_command_results_asset ON command_results(asset_id)",
        "CREATE INDEX IF NOT EXISTS idx_ipam_addresses_subnet ON ipam_addresses(subnet_id)",
        "CREATE INDEX IF NOT EXISTS idx_ipam_addresses_ip ON ipam_addresses(ip_address)",
        "CREATE INDEX IF NOT EXISTS idx_ipam_addresses_mac ON ipam_addresses(mac_address)",
        "CREATE INDEX IF NOT EXISTS idx_ipam_addresses_status ON ipam_addresses(status)",
        "CREATE INDEX IF NOT EXISTS idx_broadband_status ON broadband_contracts(status)",
        "CREATE INDEX IF NOT EXISTS idx_broadband_end ON broadband_contracts(contract_end)",
    ]
    with engine.connect() as conn:
        for idx_sql in _INDEXES:
            try:
                conn.execute(text(idx_sql))
            except Exception:
                pass
        conn.commit()


def create_db_and_tables():
    from app.models import asset, scan_task, iperf_task, broadband, topology, user  # noqa: F401
    from app.models import command, config_backup, inspection, ipam  # noqa: F401
    SQLModel.metadata.create_all(engine)
    if "sqlite" in settings.DATABASE_URL:
        _migrate_columns()
        _ensure_indexes()


def get_session():
    with Session(engine) as session:
        yield session
