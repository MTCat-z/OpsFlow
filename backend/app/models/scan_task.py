from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class ScanTaskBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    target: str = Field(max_length=500)
    scan_type: str = Field(default='ping', max_length=20)
    ports: Optional[str] = Field(default=None, max_length=200)
    arguments: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=200)

class ScanTask(ScanTaskBase, table=True):
    __tablename__ = 'scan_tasks'
    id: Optional[int] = Field(default=None, primary_key=True)
    celery_task_id: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default='pending', max_length=20)
    progress: int = Field(default=0)
    result_json: Optional[str] = Field(default=None)
    host_count: int = Field(default=0)
    port_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScanTaskCreate(ScanTaskBase):
    pass

class ScanTaskRead(ScanTaskBase):
    id: int
    celery_task_id: Optional[str]
    status: str
    progress: int
    host_count: int
    port_count: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

class ScanTaskResult(ScanTaskRead):
    result_json: Optional[str]
