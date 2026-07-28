from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class InspectionPlanBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(..., max_length=100)
    scope: str = Field(default="assets", max_length=50)
    schedule_cron: str = Field(default="0 9 * * *", max_length=100)
    checks: str = Field(default="ping,port", max_length=500)
    notify_dingtalk: bool = Field(default=True)
    enabled: bool = Field(default=True)
    notes: Optional[str] = Field(default=None, max_length=1000)


class InspectionPlan(InspectionPlanBase, table=True):
    __tablename__ = "inspection_plans"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InspectionRunBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    plan_id: Optional[int] = Field(default=None, index=True)
    status: str = Field(default="pending", max_length=20, index=True)
    summary: Optional[str] = Field(default=None, max_length=1000)
    report_json: Optional[str] = Field(default=None)
    exception_count: int = Field(default=0)
    notified: bool = Field(default=False)


class InspectionRun(InspectionRunBase, table=True):
    __tablename__ = "inspection_runs"
    id: Optional[int] = Field(default=None, primary_key=True)
    celery_task_id: Optional[str] = Field(default=None, max_length=100)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class InspectionPlanCreate(InspectionPlanBase):
    pass


class InspectionPlanUpdate(SQLModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    schedule_cron: Optional[str] = None
    checks: Optional[str] = None
    notify_dingtalk: Optional[bool] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class InspectionPlanRead(InspectionPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime


class InspectionRunRead(InspectionRunBase):
    id: int
    celery_task_id: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
