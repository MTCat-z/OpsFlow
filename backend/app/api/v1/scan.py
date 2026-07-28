from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.scan_task import ScanTask, ScanTaskCreate, ScanTaskRead, ScanTaskResult
from app.tasks.scan_tasks import run_nmap_scan

router = APIRouter()

@router.post('/start', response_model=ScanTaskRead, status_code=201)
def start_scan(task_in: ScanTaskCreate, session: Session=Depends(get_session), org_id: Optional[int]=Depends(get_current_org)):
    task = ScanTask.model_validate(task_in)
    task.org_id = org_id
    session.add(task); session.commit(); session.refresh(task)
    def _send_task():
        """在线程中发送 Celery 任务，避免阻塞主线程"""
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.scan_tasks.run_nmap_scan', args=[task.id], countdown=2)
        except Exception:
            pass
    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    task.status = 'pending'
    session.add(task); session.commit(); session.refresh(task)
    return ScanTaskRead.model_validate(task)

@router.get('/tasks', response_model=dict)
def list_tasks(page: int=Query(1,ge=1), size: int=Query(20,ge=1,le=100), status: Optional[str]=None, org_id: Optional[int]=Depends(get_current_org), session: Session=Depends(get_session)):
    q = select(ScanTask).order_by(ScanTask.created_at.desc())
    if org_id is not None: q = q.where(ScanTask.org_id == org_id)
    if status: q = q.where(ScanTask.status==status)
    total = len(session.exec(q).all())
    tasks = session.exec(q.offset((page-1)*size).limit(size)).all()
    return {'total': total, 'page': page, 'size': size, 'items': [ScanTaskRead.model_validate(t) for t in tasks]}

@router.get('/tasks/{task_id}', response_model=ScanTaskResult)
def get_task(task_id: int, session: Session=Depends(get_session)):
    task = session.get(ScanTask, task_id)
    if not task: raise HTTPException(404, '任务不存在')
    return ScanTaskResult.model_validate(task)

@router.delete('/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, session: Session=Depends(get_session)):
    task = session.get(ScanTask, task_id)
    if not task: raise HTTPException(404, '任务不存在')
    if task.celery_task_id and task.status in ('pending','running'):
        try:
            from app.tasks.worker import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except: pass
    session.delete(task); session.commit()
