from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CommandBatchBase(SQLModel):
    name: str = Field(..., max_length=100)
    asset_ids: str = Field(default="", max_length=1000)
    commands: str = Field(default="", max_length=4000)
    mode: str = Field(default="script", max_length=20)
    status: str = Field(default="draft", max_length=20)
    summary: Optional[str] = Field(default=None, max_length=1000)


class CommandBatch(CommandBatchBase, table=True):
    __tablename__ = "command_batches"
    id: Optional[int] = Field(default=None, primary_key=True)
    celery_task_id: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)


class CommandResultBase(SQLModel):
    batch_id: int = Field(index=True)
    asset_id: Optional[int] = Field(default=None, index=True)
    asset_name: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="pending", max_length=20)
    output: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None, max_length=1000)


class CommandResult(CommandResultBase, table=True):
    __tablename__ = "command_results"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommandBatchCreate(CommandBatchBase):
    pass


class CommandBatchUpdate(SQLModel):
    name: Optional[str] = None
    asset_ids: Optional[str] = None
    commands: Optional[str] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None


class CommandBatchRead(CommandBatchBase):
    id: int
    celery_task_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class CommandResultRead(CommandResultBase):
    id: int
    created_at: datetime
