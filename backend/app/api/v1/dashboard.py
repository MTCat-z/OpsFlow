from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.models.asset import Asset
from app.models.broadband import BroadbandContract
from app.models.command import CommandBatch
from app.models.config_backup import ConfigBackupJob, ConfigSnapshot
from app.models.inspection import InspectionPlan, InspectionRun
from app.models.ipam import IpamAddress, IpamSubnet
from app.models.iperf_task import IperfTask
from app.models.scan_task import ScanTask
from app.models.topology import TopologyDiscoveryTask, TopologyNode

router = APIRouter()


@router.get("/overview")
def overview(session: Session = Depends(get_session)):
    today = date.today()

    # 使用 COUNT 聚合查询，避免全表加载
    asset_total = session.exec(select(func.count(Asset.id))).one()
    asset_active = session.exec(select(func.count(Asset.id)).where(Asset.status == "active")).one()
    scan_total = session.exec(select(func.count(ScanTask.id))).one()
    scan_running = session.exec(select(func.count(ScanTask.id)).where(ScanTask.status == "running")).one()
    iperf_total = session.exec(select(func.count(IperfTask.id))).one()
    iperf_running = session.exec(select(func.count(IperfTask.id)).where(IperfTask.status == "running")).one()
    topo_nodes = session.exec(select(func.count(TopologyNode.id))).one()
    topo_tasks = session.exec(select(func.count(TopologyDiscoveryTask.id))).one()

    bb_total = session.exec(select(func.count(BroadbandContract.id))).one()
    bb_annual = session.exec(
        select(func.coalesce(func.sum(BroadbandContract.annual_cost), 0))
        .where(BroadbandContract.status == "active")
    ).one()

    plan_count = session.exec(select(func.count(InspectionPlan.id))).one()
    plan_enabled = session.exec(select(func.count(InspectionPlan.id)).where(InspectionPlan.enabled == True)).one()
    run_total = session.exec(select(func.count(InspectionRun.id))).one()
    # 异常总数
    exception_sum = session.exec(
        select(func.coalesce(func.sum(InspectionRun.exception_count), 0))
    ).one()

    backup_jobs = session.exec(select(func.count(ConfigBackupJob.id))).one()
    snapshots = session.exec(select(func.count(ConfigSnapshot.id))).one()
    cmd_batches = session.exec(select(func.count(CommandBatch.id))).one()

    subnet_count = session.exec(select(func.count(IpamSubnet.id))).one()
    addr_count = session.exec(select(func.count(IpamAddress.id))).one()
    conflict_count = session.exec(select(func.count(IpamAddress.id)).where(IpamAddress.status == "conflict")).one()

    # 30 天内到期宽带
    expiring = session.exec(
        select(BroadbandContract).where(
            BroadbandContract.status == "active",
            BroadbandContract.contract_end >= today,
        )
    ).all()
    expiring_30 = [c for c in expiring if (c.contract_end - today).days <= 30]

    # 最近巡检报告
    recent_runs = session.exec(
        select(InspectionRun).order_by(InspectionRun.created_at.desc()).limit(5)
    ).all()

    # 资产类型分布
    type_rows = session.exec(
        select(Asset.device_type, func.count(Asset.id))
        .group_by(Asset.device_type)
    ).all()
    asset_types = {row[0] or "未分类": row[1] for row in type_rows}

    return {
        "assets": {"total": asset_total, "active": asset_active},
        "network_tasks": {
            "scans": scan_total,
            "scan_running": scan_running,
            "iperf": iperf_total,
            "iperf_running": iperf_running,
            "topology_nodes": topo_nodes,
            "topology_tasks": topo_tasks,
        },
        "broadband": {
            "contracts": bb_total,
            "expiring_30d": len(expiring_30),
            "annual_cost": round(float(bb_annual or 0), 2),
            "expiring_list": [
                {
                    "id": c.id,
                    "provider": c.provider,
                    "circuit_id": c.circuit_id,
                    "contract_end": str(c.contract_end),
                    "days_remaining": (c.contract_end - today).days,
                }
                for c in sorted(expiring_30, key=lambda x: x.contract_end)[:5]
            ],
        },
        "inspection": {
            "plans": plan_count,
            "enabled_plans": plan_enabled,
            "runs": run_total,
            "exceptions": int(exception_sum or 0),
            "recent_runs": [
                {
                    "id": r.id,
                    "plan_id": r.plan_id,
                    "status": r.status,
                    "exception_count": r.exception_count,
                    "summary": r.summary,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recent_runs
            ],
        },
        "automation": {
            "backup_jobs": backup_jobs,
            "config_snapshots": snapshots,
            "command_batches": cmd_batches,
        },
        "ipam": {
            "subnets": subnet_count,
            "addresses": addr_count,
            "conflicts": conflict_count,
        },
        "asset_types": asset_types,
    }
