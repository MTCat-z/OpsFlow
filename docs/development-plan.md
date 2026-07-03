# OpsFlow Feature Development Plan

## Scope

This plan covers the confirmed feature set:

1. 自动化巡检: scheduled checks, inspection reports, DingTalk exception summaries.
2. 配置备份: scheduled SSH configuration pulls, versioned diffs, full-text search.
3. 批量命令执行: select assets, run command scripts, compare summarized output.
4. IPAM: subnet registry plus Nmap/ARP discovery for DHCP-friendly address tracking.
5. 运维数据大屏: global overview across assets, scans, broadband, inspections, and related modules.

## Phase 1: Module Foundations

- Add backend models and protected APIs for the five new modules.
- Add frontend routes, navigation entries, and module pages.
- Add a global dashboard API and make it the default landing page.
- Keep long-running network actions as queued tasks, consistent with existing scan, iperf, topology, and broadband renewal work.

## Phase 2: Automation

- Implement inspection execution workers and DingTalk exception summaries.
- Implement configuration backup workers using existing asset credentials.
- Implement batch command execution workers with per-asset result capture.
- Implement IPAM discovery workers that reconcile scanned addresses into registered subnets.

## Phase 3: Search, Diff, And Reporting

- Add configuration snapshot diff views and searchable snapshot content.
- Add inspection report detail pages and trend summaries.
- Add batch command result comparison views.
- Expand the dashboard with risk and workload indicators from the new modules.

## Local Test Target

- Backend API starts and initializes the expanded SQLite schema.
- Frontend builds successfully and exposes all new navigation entries.
- Local browser can load the dashboard and new module pages.
