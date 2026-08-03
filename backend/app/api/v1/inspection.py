from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.core.auth import get_current_org, get_current_user, check_org_access, require_org_admin
from app.models.user import User
from app.models.inspection import (
    InspectionPlan,
    InspectionPlanCreate,
    InspectionPlanRead,
    InspectionPlanUpdate,
    InspectionRun,
    InspectionRunRead,
)

router = APIRouter()


@router.get("/dashboard")
def inspection_dashboard(session: Session = Depends(get_session)):
    plan_count = session.exec(select(func.count(InspectionPlan.id))).one()
    enabled_count = session.exec(select(func.count(InspectionPlan.id)).where(InspectionPlan.enabled == True)).one()
    run_count = session.exec(select(func.count(InspectionRun.id))).one()
    failed_count = session.exec(select(func.count(InspectionRun.id)).where(InspectionRun.status == "failed")).one()
    latest_runs = session.exec(select(InspectionRun).order_by(InspectionRun.created_at.desc()).limit(5)).all()
    # 异常总数
    runs = session.exec(select(InspectionRun.exception_count)).all()
    total_exceptions = sum(r or 0 for r in runs)
    return {
        "plans": plan_count,
        "enabled_plans": enabled_count,
        "runs": run_count,
        "failed_runs": failed_count,
        "exceptions": total_exceptions,
        "latest_runs": latest_runs,
    }


@router.get("/plans", response_model=dict)
def list_plans(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), org_id: Optional[int] = Depends(get_current_org), session: Session = Depends(get_session)):
    q = select(InspectionPlan)
    if org_id is not None:
        q = q.where(InspectionPlan.org_id == org_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/plans", response_model=InspectionPlanRead, status_code=201)
def create_plan(data: InspectionPlanCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    plan = InspectionPlan.model_validate(data)
    plan.org_id = org_id
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


@router.get("/plans/{plan_id}", response_model=InspectionPlanRead)
def get_plan(plan_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    plan = session.get(InspectionPlan, plan_id)
    if not plan or not check_org_access(plan, current_user):
        raise HTTPException(404, "inspection plan not found")
    return plan


@router.put("/plans/{plan_id}", response_model=InspectionPlanRead)
def update_plan(plan_id: int, data: InspectionPlanUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    plan = session.get(InspectionPlan, plan_id)
    if not plan or not check_org_access(plan, current_user):
        raise HTTPException(404, "inspection plan not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    plan.updated_at = datetime.utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    plan = session.get(InspectionPlan, plan_id)
    if not plan or not check_org_access(plan, current_user):
        raise HTTPException(404, "inspection plan not found")
    session.delete(plan)
    session.commit()


@router.post("/plans/{plan_id}/run", response_model=InspectionRunRead, status_code=201)
def run_plan(plan_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user), admin: User = Depends(require_org_admin)):
    """手动触发巡检方案执行"""
    plan = session.get(InspectionPlan, plan_id)
    if not plan or not check_org_access(plan, current_user):
        raise HTTPException(404, "inspection plan not found")
    run = InspectionRun(plan_id=plan.id, status="pending")
    session.add(run)
    session.commit()
    session.refresh(run)

    def _send_task():
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.inspection_tasks.run_inspection', args=[plan.id, run.id], countdown=2)
        except Exception:
            pass

    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    return run


@router.get("/runs", response_model=dict)
def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    plan_id: Optional[int] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q = select(InspectionRun)
    if org_id is not None:
        q = q.where(InspectionRun.org_id == org_id)
    if status:
        q = q.where(InspectionRun.status == status)
    if plan_id:
        q = q.where(InspectionRun.plan_id == plan_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(InspectionRun.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/runs/{run_id}", response_model=InspectionRunRead)
def get_run(run_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    run = session.get(InspectionRun, run_id)
    if not run or not check_org_access(run, current_user):
        raise HTTPException(404, "inspection run not found")
    return run
