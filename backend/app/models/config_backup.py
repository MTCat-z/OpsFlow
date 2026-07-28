from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ConfigBackupJobBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(..., max_length=100)
    asset_filter: Optional[str] = Field(default=None, max_length=500)
    schedule_cron: str = Field(default="0 2 * * *", max_length=100)
    command: str = Field(default="show running-config", max_length=500)
    enabled: bool = Field(default=True)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ConfigBackupJob(ConfigBackupJobBase, table=True):
    __tablename__ = "config_backup_jobs"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConfigSnapshotBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    job_id: Optional[int] = Field(default=None, index=True)
    asset_id: Optional[int] = Field(default=None, index=True)
    asset_name: Optional[str] = Field(default=None, max_length=100)
    config_text: str = Field(default="")
    content_hash: Optional[str] = Field(default=None, max_length=128, index=True)
    diff_summary: Optional[str] = Field(default=None, max_length=1000)
    status: str = Field(default="captured", max_length=20)


class ConfigSnapshot(ConfigSnapshotBase, table=True):
    __tablename__ = "config_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ConfigBackupJobCreate(ConfigBackupJobBase):
    pass


class ConfigBackupJobUpdate(SQLModel):
    name: Optional[str] = None
    asset_filter: Optional[str] = None
    schedule_cron: Optional[str] = None
    command: Optional[str] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class ConfigBackupJobRead(ConfigBackupJobBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ConfigSnapshotRead(ConfigSnapshotBase):
    id: int
    created_at: datetime
