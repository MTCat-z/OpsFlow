from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.asset import Asset
from app.models.broadband import BroadbandContract
from app.models.command import CommandBatch
from app.models.config_backup import ConfigBackupJob, ConfigSnapshot
from app.models.inspection import InspectionPlan, InspectionRun
from app.models.ipam import IpamAddress, IpamSubnet
from app.models.iperf_task import IperfTask
from app.models.scan_task import ScanTask
from app.models.topology import TopologyDiscoveryTask, TopologyNode
from app.services.broadband_renewal import get_next_renewal

router = APIRouter()


def _org_q(stmt, model, org_id):
    """如果 org_id 不为 None，添加 org_id 过滤条件"""
    if org_id is not None:
        return stmt.where(model.org_id == org_id)
    return stmt


@router.get("/overview")
def overview(session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    today = date.today()

    # 使用 COUNT 聚合查询，避免全表加载
    asset_total = session.exec(_org_q(select(func.count(Asset.id)), Asset, org_id)).one()
    asset_active = session.exec(_org_q(select(func.count(Asset.id)).where(Asset.status == "active"), Asset, org_id)).one()
    scan_total = session.exec(_org_q(select(func.count(ScanTask.id)), ScanTask, org_id)).one()
    scan_running = session.exec(_org_q(select(func.count(ScanTask.id)).where(ScanTask.status == "running"), ScanTask, org_id)).one()
    iperf_total = session.exec(_org_q(select(func.count(IperfTask.id)), IperfTask, org_id)).one()
    iperf_running = session.exec(_org_q(select(func.count(IperfTask.id)).where(IperfTask.status == "running"), IperfTask, org_id)).one()
    topo_nodes = session.exec(_org_q(select(func.count(TopologyNode.id)), TopologyNode, org_id)).one()
    topo_tasks = session.exec(_org_q(select(func.count(TopologyDiscoveryTask.id)), TopologyDiscoveryTask, org_id)).one()

    bb_total = session.exec(_org_q(select(func.count(BroadbandContract.id)), BroadbandContract, org_id)).one()
    bb_annual = session.exec(
        _org_q(
            select(func.coalesce(func.sum(BroadbandContract.annual_cost), 0))
            .where(BroadbandContract.status == "active"),
            BroadbandContract, org_id,
        )
    ).one()

    plan_count = session.exec(_org_q(select(func.count(InspectionPlan.id)), InspectionPlan, org_id)).one()
    plan_enabled = session.exec(_org_q(select(func.count(InspectionPlan.id)).where(InspectionPlan.enabled == True), InspectionPlan, org_id)).one()
    run_total = session.exec(_org_q(select(func.count(InspectionRun.id)), InspectionRun, org_id)).one()
    # 异常总数
    exception_sum = session.exec(
        _org_q(select(func.coalesce(func.sum(InspectionRun.exception_count), 0)), InspectionRun, org_id)
    ).one()

    backup_jobs = session.exec(_org_q(select(func.count(ConfigBackupJob.id)), ConfigBackupJob, org_id)).one()
    snapshots = session.exec(_org_q(select(func.count(ConfigSnapshot.id)), ConfigSnapshot, org_id)).one()
    cmd_batches = session.exec(_org_q(select(func.count(CommandBatch.id)), CommandBatch, org_id)).one()

    subnet_count = session.exec(_org_q(select(func.count(IpamSubnet.id)), IpamSubnet, org_id)).one()
    addr_count = session.exec(_org_q(select(func.count(IpamAddress.id)), IpamAddress, org_id)).one()
    conflict_count = session.exec(_org_q(select(func.count(IpamAddress.id)).where(IpamAddress.status == "conflict"), IpamAddress, org_id)).one()

    # 30 天内到期宽带
    expiring = session.exec(
        _org_q(
            select(BroadbandContract).where(
                BroadbandContract.status == "active",
                BroadbandContract.contract_end >= today,
            ),
            BroadbandContract, org_id,
        )
    ).all()
    expiring_30 = [c for c in expiring if (c.contract_end - today).days <= 30]

    # 按续费周期对齐的即将到期宽带
    renewal_infos = []
    for c in expiring:
        r = get_next_renewal(c, today)
        renewal_infos.append({
            "provider": c.provider,
            "circuit_id": c.circuit_id,
            "next_renewal_deadline": r["next_deadline"].isoformat(),
            "next_renewal_days": r["days_remaining"],
        })
    expiring_renewal_30 = sum(1 for r in renewal_infos if 0 <= r["next_renewal_days"] <= 30)
    expiring_renewal_list = sorted(
        [r for r in renewal_infos if 0 <= r["next_renewal_days"] <= 30],
        key=lambda x: x["next_renewal_days"],
    )[:5]

    # 最近巡检报告
    recent_runs = session.exec(
        _org_q(select(InspectionRun).order_by(InspectionRun.created_at.desc()).limit(5), InspectionRun, org_id)
    ).all()

    # 资产类型分布
    type_rows = session.exec(
        _org_q(select(Asset.device_type, func.count(Asset.id)).group_by(Asset.device_type), Asset, org_id)
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
            "expiring_renewal_30d": expiring_renewal_30,
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
            "expiring_renewal_list": expiring_renewal_list,
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
