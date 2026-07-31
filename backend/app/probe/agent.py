"""
OpsFlow 探针 Agent - 部署在各分公司内网，本地执行 nmap/iperf3
通过 VPN 隧道与中心服务器通信（Pull 模式）
"""
import os
import time
import json
import subprocess
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('probe')

OPSFLOW_URL = os.getenv('OPSFLOW_URL', 'http://10.99.0.1:8000')
PROBE_KEY = os.getenv('PROBE_KEY', '')
ORG_CODE = os.getenv('ORG_CODE', '')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))

HEADERS = {
    'X-Probe-Key': PROBE_KEY,
    'X-Org-Code': ORG_CODE,
}


def run_nmap(target, scan_type='ping', ports=None, arguments=None):
    """执行 nmap 扫描"""
    import nmap
    scan_args = {
        'ping': '-sn',
        'port': '-sS --open',
        'service': '-sV --open',
        'full': '-sV -O --open',
    }.get(scan_type, '-sn')

    if arguments:
        scan_args += f' {arguments}'
    if ports and scan_type != 'ping':
        scan_args += f' -p {ports}'

    logger.info('开始扫描: %s (类型: %s, 参数: %s)', target, scan_type, scan_args)
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=target, arguments=scan_args)

        hosts = []
        for host in nm.all_hosts():
            host_info = {
                'ip': host,
                'hostname': nm[host].hostname(),
                'state': nm[host].state(),
                'ports': [],
            }
            for proto in nm[host].all_protocols():
                for port, info in nm[host][proto].items():
                    host_info['ports'].append({
                        'port': port,
                        'protocol': proto,
                        'state': info.get('state', ''),
                        'service': info.get('name', ''),
                        'product': info.get('product', ''),
                        'version': info.get('version', ''),
                    })
            hosts.append(host_info)

        port_count = sum(len(h['ports']) for h in hosts)
        result = {
            'success': True,
            'result_json': json.dumps({'hosts': hosts}, ensure_ascii=False),
            'host_count': len(hosts),
            'port_count': port_count,
        }
        logger.info('扫描完成: %d 台主机, %d 个端口', len(hosts), port_count)
        return result
    except Exception as e:
        logger.error('扫描失败: %s', e)
        return {'success': False, 'error_message': str(e)[:500]}


def run_iperf3(server_host, server_port=5201, protocol='tcp', duration=10, parallel=1, reverse=False):
    """执行 iperf3 测速"""
    cmd = ['iperf3', '-c', server_host, '-p', str(server_port),
           '-t', str(duration), '-P', str(parallel), '-J']
    if protocol == 'udp':
        cmd.extend(['-u', '-b', '0'])
    if reverse:
        cmd.append('-R')

    logger.info('开始测速: %s:%d (%s)', server_host, server_port, protocol)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)

        if proc.returncode != 0:
            return {'success': False, 'error_message': proc.stderr[:500]}

        data = json.loads(proc.stdout)
        if 'error' in data:
            return {'success': False, 'error_message': data['error']}

        result = {'success': True, 'result_json': proc.stdout}

        if protocol == 'udp':
            end = data.get('end', {})
            summary = end.get('sum', end.get('sum_sent', {}))
            bps = summary.get('bits_per_second', 0)
            result['bandwidth_mbps'] = round(bps / 1e6, 2)
            result['jitter_ms'] = round(summary.get('jitter_ms', 0), 2)
            packets = summary.get('packets', 0)
            lost = summary.get('lost_packets', 0)
            result['lost_percent'] = round(lost / packets * 100, 2) if packets > 0 else 0
        else:
            end = data.get('end', {})
            summary = end.get('sum_sent', end.get('sum', {}))
            bps = summary.get('bits_per_second', 0)
            result['bandwidth_mbps'] = round(bps / 1e6, 2)
            result['retransmits'] = summary.get('retransmits', 0)

        logger.info('测速完成: %.2f Mbps', result.get('bandwidth_mbps', 0))
        return result
    except subprocess.TimeoutExpired:
        return {'success': False, 'error_message': '测速超时'}
    except Exception as e:
        logger.error('测速失败: %s', e)
        return {'success': False, 'error_message': str(e)[:500]}


def poll_tasks():
    """从中心拉取待执行任务"""
    try:
        resp = httpx.get(
            f'{OPSFLOW_URL}/api/v1/probes/tasks',
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error('拉取任务失败: HTTP %d', resp.status_code)
            return []
        data = resp.json()
        return data.get('tasks', [])
    except Exception as e:
        logger.error('拉取任务异常: %s', e)
        return []


def submit_result(task_type, task_id, result):
    """回传任务结果"""
    try:
        resp = httpx.post(
            f'{OPSFLOW_URL}/api/v1/probes/tasks/{task_type}/{task_id}/result',
            headers=HEADERS,
            json=result,
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info('结果已回传: %s/%d', task_type, task_id)
        else:
            logger.error('回传失败: HTTP %d %s', resp.status_code, resp.text)
    except Exception as e:
        logger.error('回传异常: %s', e)


def send_heartbeat():
    """发送心跳"""
    try:
        resp = httpx.post(
            f'{OPSFLOW_URL}/api/v1/probes/heartbeat',
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            logger.debug('心跳已发送')
        else:
            logger.warning('心跳失败: HTTP %d', resp.status_code)
    except Exception as e:
        logger.warning('心跳异常: %s', e)


def main():
    logger.info('OpsFlow 探针已启动')
    logger.info('中心地址: %s', OPSFLOW_URL)
    logger.info('组织编码: %s', ORG_CODE)

    if not PROBE_KEY or not ORG_CODE:
        logger.error('缺少 PROBE_KEY 或 ORG_CODE 环境变量，请检查 .env')
        return

    while True:
        try:
            # 发送心跳
            send_heartbeat()

            # 拉取任务
            tasks = poll_tasks()
            if tasks:
                logger.info('收到 %d 个任务', len(tasks))

            for task in tasks:
                task_type = task['type']
                task_id = task['task_id']

                if task_type == 'scan':
                    result = run_nmap(
                        target=task['target'],
                        scan_type=task.get('scan_type', 'ping'),
                        ports=task.get('ports'),
                        arguments=task.get('arguments'),
                    )
                    submit_result('scan', task_id, result)
                elif task_type == 'iperf':
                    result = run_iperf3(
                        server_host=task['server_host'],
                        server_port=task.get('server_port', 5201),
                        protocol=task.get('protocol', 'tcp'),
                        duration=task.get('duration', 10),
                        parallel=task.get('parallel', 1),
                        reverse=task.get('reverse', False),
                    )
                    submit_result('iperf', task_id, result)

        except Exception as e:
            logger.error('主循环异常: %s', e)

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
