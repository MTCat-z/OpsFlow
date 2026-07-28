from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class IperfTaskBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    server_host: str = Field(max_length=100)
    server_port: int = Field(default=5201)
    protocol: str = Field(default='tcp', max_length=10)
    duration: int = Field(default=10)
    parallel: int = Field(default=1)
    reverse: bool = Field(default=False)
    description: Optional[str] = Field(default=None, max_length=200)

class IperfTask(IperfTaskBase, table=True):
    __tablename__ = 'iperf_tasks'
    id: Optional[int] = Field(default=None, primary_key=True)
    celery_task_id: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default='pending', max_length=20)
    bandwidth_mbps: Optional[float] = Field(default=None)
    jitter_ms: Optional[float] = Field(default=None)
    lost_percent: Optional[float] = Field(default=None)
    retransmits: Optional[int] = Field(default=None)
    result_json: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class IperfTaskCreate(IperfTaskBase):
    pass

class IperfTaskRead(IperfTaskBase):
    id: int
    celery_task_id: Optional[str]
    status: str
    bandwidth_mbps: Optional[float]
    jitter_ms: Optional[float]
    lost_percent: Optional[float]
    retransmits: Optional[int]
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

class IperfTaskResult(IperfTaskRead):
    result_json: Optional[str]
