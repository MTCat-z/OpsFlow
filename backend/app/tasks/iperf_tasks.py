"""
测速任务执行 -- 已迁移至探针 Agent 本地执行（ADR-0003）

历史：run_iperf_test 曾由中心 Celery worker 在中心服务器本地执行 iperf3，
现已移除。测速任务保持 pending 状态，由各组织探针通过 /probes/tasks 拉取
并在分公司本地网络执行。本文件保留为空占位，避免历史 import 报错。
"""
