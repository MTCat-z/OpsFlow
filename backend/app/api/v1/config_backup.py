from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, func, select

from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.config_backup import (
    ConfigBackupJob,
    ConfigBackupJobCreate,
    ConfigBackupJobRead,
    ConfigBackupJobUpdate,
    ConfigSnapshot,
    ConfigSnapshotRead,
)

router = APIRouter()


@router.get("/dashboard")
def backup_dashboard(session: Session = Depends(get_session)):
    job_count = session.exec(select(func.count(ConfigBackupJob.id))).one()
    enabled_count = session.exec(select(func.count(ConfigBackupJob.id)).where(ConfigBackupJob.enabled == True)).one()
    snap_count = session.exec(select(func.count(ConfigSnapshot.id))).one()
    failed_count = session.exec(select(func.count(ConfigSnapshot.id)).where(ConfigSnapshot.status == "failed")).one()
    return {
        "jobs": job_count,
        "enabled_jobs": enabled_count,
        "snapshots": snap_count,
        "failed_snapshots": failed_count,
    }


@router.get("/jobs", response_model=dict)
def list_jobs(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), org_id: Optional[int] = Depends(get_current_org), session: Session = Depends(get_session)):
    q = select(ConfigBackupJob)
    if org_id is not None:
        q = q.where(ConfigBackupJob.org_id == org_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/jobs", response_model=ConfigBackupJobRead, status_code=201)
def create_job(data: ConfigBackupJobCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    job = ConfigBackupJob.model_validate(data)
    job.org_id = org_id
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.put("/jobs/{job_id}", response_model=ConfigBackupJobRead)
def update_job(job_id: int, data: ConfigBackupJobUpdate, session: Session = Depends(get_session)):
    job = session.get(ConfigBackupJob, job_id)
    if not job:
        raise HTTPException(404, "config backup job not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(job, key, value)
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(ConfigBackupJob, job_id)
    if not job:
        raise HTTPException(404, "config backup job not found")
    session.delete(job)
    session.commit()


@router.post("/jobs/{job_id}/run", status_code=201)
def run_job(job_id: int, session: Session = Depends(get_session)):
    """手动触发配置备份任务"""
    job = session.get(ConfigBackupJob, job_id)
    if not job:
        raise HTTPException(404, "config backup job not found")

    def _send_task():
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.config_backup_tasks.run_config_backup', args=[job.id], countdown=2)
        except Exception:
            pass

    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    return {"job_id": job.id, "status": "queued"}


@router.get("/snapshots", response_model=dict)
def list_snapshots(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    asset_id: Optional[int] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q = select(ConfigSnapshot)
    if org_id is not None:
        q = q.where(ConfigSnapshot.org_id == org_id)
    if keyword:
        q = q.where(
            col(ConfigSnapshot.asset_name).contains(keyword)
            | col(ConfigSnapshot.config_text).contains(keyword)
            | col(ConfigSnapshot.diff_summary).contains(keyword)
        )
    if asset_id:
        q = q.where(ConfigSnapshot.asset_id == asset_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(ConfigSnapshot.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/snapshots/{snapshot_id}", response_model=ConfigSnapshotRead)
def get_snapshot(snapshot_id: int, session: Session = Depends(get_session)):
    snapshot = session.get(ConfigSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(404, "config snapshot not found")
    return snapshot


@router.get("/snapshots/{snapshot_id}/diff")
def get_snapshot_diff(snapshot_id: int, session: Session = Depends(get_session)):
    """获取快照与上一版本的差异"""
    snapshot = session.get(ConfigSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(404, "config snapshot not found")

    # 查找同资产的上一份快照
    prev = session.exec(
        select(ConfigSnapshot)
        .where(ConfigSnapshot.asset_id == snapshot.asset_id)
        .where(ConfigSnapshot.created_at < snapshot.created_at)
        .order_by(ConfigSnapshot.created_at.desc())
        .limit(1)
    ).first()

    if not prev:
        return {"current_id": snapshot.id, "previous_id": None, "diff": "无上一版本可供对比", "changed": False}

    changed = prev.content_hash != snapshot.content_hash if snapshot.content_hash and prev.content_hash else True
    return {
        "current_id": snapshot.id,
        "previous_id": prev.id,
        "diff": snapshot.diff_summary or "无差异记录",
        "changed": changed,
        "current_hash": snapshot.content_hash,
        "previous_hash": prev.content_hash,
        "previous_created_at": prev.created_at.isoformat() if prev.created_at else None,
    }
