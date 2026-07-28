from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.command import CommandBatch, CommandBatchCreate, CommandBatchRead, CommandBatchUpdate, CommandResult, CommandResultRead

router = APIRouter()


@router.get("/dashboard")
def commands_dashboard(session: Session = Depends(get_session)):
    batch_count = session.exec(select(func.count(CommandBatch.id))).one()
    running_count = session.exec(select(func.count(CommandBatch.id)).where(CommandBatch.status == "running")).one()
    completed_count = session.exec(select(func.count(CommandBatch.id)).where(CommandBatch.status == "completed")).one()
    failed_count = session.exec(select(func.count(CommandResult.id)).where(CommandResult.status == "failed")).one()
    return {
        "batches": batch_count,
        "running_batches": running_count,
        "completed_batches": completed_count,
        "failed_results": failed_count,
    }


@router.get("/batches", response_model=dict)
def list_batches(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q = select(CommandBatch)
    if org_id is not None:
        q = q.where(CommandBatch.org_id == org_id)
    if status:
        q = q.where(CommandBatch.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(CommandBatch.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/batches", response_model=CommandBatchRead, status_code=201)
def create_batch(data: CommandBatchCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    batch = CommandBatch.model_validate(data)
    batch.org_id = org_id
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


@router.get("/batches/{batch_id}", response_model=CommandBatchRead)
def get_batch(batch_id: int, session: Session = Depends(get_session)):
    batch = session.get(CommandBatch, batch_id)
    if not batch:
        raise HTTPException(404, "command batch not found")
    return batch


@router.put("/batches/{batch_id}", response_model=CommandBatchRead)
def update_batch(batch_id: int, data: CommandBatchUpdate, session: Session = Depends(get_session)):
    batch = session.get(CommandBatch, batch_id)
    if not batch:
        raise HTTPException(404, "command batch not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(batch, key, value)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


@router.delete("/batches/{batch_id}", status_code=204)
def delete_batch(batch_id: int, session: Session = Depends(get_session)):
    batch = session.get(CommandBatch, batch_id)
    if not batch:
        raise HTTPException(404, "command batch not found")
    if batch.celery_task_id and batch.status in ("pending", "running"):
        try:
            from app.tasks.worker import celery_app
            celery_app.control.revoke(batch.celery_task_id, terminate=True)
        except Exception:
            pass
    session.delete(batch)
    session.commit()


@router.post("/batches/{batch_id}/execute")
def execute_batch(batch_id: int, session: Session = Depends(get_session)):
    """执行批量命令任务（先检查危险命令）"""
    from app.services.command_guard import check_dangerous_commands

    batch = session.get(CommandBatch, batch_id)
    if not batch:
        raise HTTPException(404, "command batch not found")
    if batch.status not in ("draft", "failed"):
        raise HTTPException(400, f"当前状态 {batch.status} 不可执行")

    # 危险命令检查
    guard_result = check_dangerous_commands(batch.commands)
    if not guard_result["safe"]:
        return {"safe": False, "blocked": guard_result["blocked"], "reasons": guard_result["reasons"]}

    batch.status = "pending"
    session.add(batch)
    session.commit()

    def _send_task():
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.command_tasks.run_command_batch', args=[batch.id], countdown=2)
        except Exception:
            pass

    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    return {"safe": True, "batch_id": batch.id, "status": "queued"}


@router.get("/batches/{batch_id}/results", response_model=list[CommandResultRead])
def list_results(batch_id: int, session: Session = Depends(get_session)):
    return session.exec(select(CommandResult).where(CommandResult.batch_id == batch_id)).all()
