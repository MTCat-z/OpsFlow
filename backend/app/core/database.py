from sqlmodel import SQLModel, create_engine, Session, text
from app.core.config import settings

_is_sqlite = "sqlite" in settings.DATABASE_URL
_is_postgres = "postgresql" in settings.DATABASE_URL

connect_args = {}
if _is_sqlite:
    connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)


def _get_existing_columns(conn, table: str) -> set:
    """获取表已有的列名，兼容 SQLite 和 PostgreSQL"""
    if _is_sqlite:
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        return {row[1] for row in result}
    else:
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :table"
        ), {"table": table})
        return {row[0] for row in result}


def _migrate_columns():
    """为已有表自动补充缺失列（create_all 不会 ALTER TABLE）"""
    _MIGRATIONS = {
        'assets': [
            ('ssh_private_key_encrypted', 'VARCHAR'),
            ('auth_type', "VARCHAR(20) DEFAULT 'password'"),
            ('org_id', 'INTEGER'),
        ],
        'broadband_contracts': [
            ('renewal_cycle', "VARCHAR(20) DEFAULT 'annual'"),
            ('renewal_cost', 'FLOAT'),
            ('last_renewed_date', 'DATE'),
            ('org_id', 'INTEGER'),
        ],
        'users': [
            ('org_id', 'INTEGER'),
        ],
        'scan_tasks': [
            ('org_id', 'INTEGER'),
        ],
        'iperf_tasks': [
            ('org_id', 'INTEGER'),
        ],
        'topology_nodes': [
            ('org_id', 'INTEGER'),
        ],
        'topology_edges': [
            ('org_id', 'INTEGER'),
        ],
        'ipam_subnets': [
            ('org_id', 'INTEGER'),
        ],
        'ipam_addresses': [
            ('org_id', 'INTEGER'),
        ],
        'inspection_plans': [
            ('org_id', 'INTEGER'),
        ],
        'inspection_runs': [
            ('org_id', 'INTEGER'),
        ],
        'config_backup_jobs': [
            ('org_id', 'INTEGER'),
        ],
        'config_snapshots': [
            ('org_id', 'INTEGER'),
        ],
        'command_batches': [
            ('org_id', 'INTEGER'),
        ],
        'command_results': [
            ('org_id', 'INTEGER'),
        ],
    }
    with engine.connect() as conn:
        for table, columns in _MIGRATIONS.items():
            existing = _get_existing_columns(conn, table)
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
        "CREATE INDEX IF NOT EXISTS idx_assets_org ON assets(org_id)",
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
        "CREATE INDEX IF NOT EXISTS idx_broadband_org ON broadband_contracts(org_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id)",
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
    from app.models import organization  # noqa: F401
    SQLModel.metadata.create_all(engine)
    # SQLite 和 PostgreSQL 都需要自动迁移补充列
    _migrate_columns()
    _ensure_indexes()


def get_session():
    with Session(engine) as session:
        yield session
