from fastapi import APIRouter, Depends

from app.api.v1 import (
    assets,
    audit,
    auth,
    broadband,
    commands,
    config_backup,
    dashboard,
    diagnostics,
    inspection,
    ipam,
    iperf,
    scan,
    topology,
    users,
    zabbix,
)
from app.core.auth import get_current_user

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

_auth = [Depends(get_current_user)]
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=_auth)
api_router.include_router(audit.router, prefix="/audit", tags=["audit"], dependencies=_auth)
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=_auth)
api_router.include_router(assets.router, prefix="/assets", tags=["assets"], dependencies=_auth)
api_router.include_router(scan.router, prefix="/scan", tags=["scan"], dependencies=_auth)
api_router.include_router(iperf.router, prefix="/iperf", tags=["iperf"], dependencies=_auth)
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"], dependencies=_auth)
api_router.include_router(broadband.router, prefix="/broadband", tags=["broadband"], dependencies=_auth)
api_router.include_router(topology.router, prefix="/topology", tags=["topology"], dependencies=_auth)
api_router.include_router(zabbix.router, prefix="/zabbix", tags=["zabbix"], dependencies=_auth)
api_router.include_router(inspection.router, prefix="/inspection", tags=["inspection"], dependencies=_auth)
api_router.include_router(config_backup.router, prefix="/config-backup", tags=["config-backup"], dependencies=_auth)
api_router.include_router(commands.router, prefix="/commands", tags=["commands"], dependencies=_auth)
api_router.include_router(ipam.router, prefix="/ipam", tags=["ipam"], dependencies=_auth)
