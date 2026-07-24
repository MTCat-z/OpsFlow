"""
钉钉机器人 Webhook 通知服务
"""
import hashlib
import hmac
import base64
import time
import urllib.parse
import json
import logging
from typing import Optional
from datetime import date

import httpx

from app.core.config import settings
from app.models.broadband import RENEWAL_CYCLE_LABELS

logger = logging.getLogger(__name__)


def _sign_url(webhook_url: str, secret: str) -> str:
    """钉钉加签模式：HMAC-SHA256"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = '&' if '?' in webhook_url else '?'
    return f'{webhook_url}{sep}timestamp={timestamp}&sign={sign}'


def send_dingtalk_message(title: str, text: str) -> bool:
    """发送钉钉 Markdown 消息"""
    webhook_url = settings.DINGTALK_WEBHOOK_URL
    if not webhook_url:
        logger.warning('钉钉 Webhook URL 未配置')
        return False

    if settings.DINGTALK_SECRET:
        webhook_url = _sign_url(webhook_url, settings.DINGTALK_SECRET)

    payload = {
        'msgtype': 'markdown',
        'markdown': {
            'title': title,
            'text': text,
        },
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook_url, json=payload)
            data = resp.json()
            if data.get('errcode') == 0:
                logger.info('钉钉通知发送成功: %s', title)
                return True
            else:
                logger.error('钉钉通知发送失败: %s', data)
                return False
    except Exception as e:
        logger.error('钉钉通知发送异常: %s', e)
        return False


def send_renewal_reminder(
    provider: str,
    circuit_id: Optional[str],
    bandwidth_mbps: int,
    location: Optional[str],
    contract_end: date,
    days_remaining: int,
    contact_name: Optional[str],
    renewal_deadline: Optional[date] = None,
    deadline_type: Optional[str] = None,
    renewal_cycle: str = 'annual',
    renewal_cost: Optional[float] = None,
    annual_cost: Optional[float] = None,
) -> bool:
    """发送宽带续费提醒"""
    urgency = '🔴 紧急' if days_remaining <= 7 else '🔔 提醒'
    cycle_label = RENEWAL_CYCLE_LABELS.get(renewal_cycle, '每年')
    is_cycle = deadline_type == 'cycle'
    if is_cycle:
        deadline_label = '周期续费截止'
        title = '宽带续费提醒'
    else:
        deadline_label = '合同到期'
        title = '宽带续费提醒'
    deadline_to_show = renewal_deadline or contract_end

    lines = [
        f'### {urgency} 宽带续费提醒',
        '',
        f'- **运营商**: {provider}',
    ]
    if circuit_id:
        lines.append(f'- **线路编号**: {circuit_id}')
    if is_cycle:
        lines.append(f'- **提醒类型**: 周期性续费')
    else:
        lines.append(f'- **提醒类型**: 合同到期续费')
    lines.extend([
        f'- **带宽**: {bandwidth_mbps} Mbps',
        f'- **续费周期**: {cycle_label}',
    ])
    if renewal_cost is not None:
        lines.append(f'- **周期费用**: {renewal_cost:.2f} 元/{cycle_label}')
    if annual_cost is not None:
        lines.append(f'- **年度费用**: {annual_cost:.2f} 元/年')
    if location:
        lines.append(f'- **位置**: {location}')
    lines.extend([
        f'- **{deadline_label}**: {deadline_to_show.strftime("%Y-%m-%d")}',
        f'- **剩余天数**: **{days_remaining} 天**',
    ])
    if is_cycle:
        lines.append(f'- **合同最终到期**: {contract_end.strftime("%Y-%m-%d")}')
    if contact_name:
        lines.append(f'- **联系人**: {contact_name}')

    lines.extend([
        '',
        '> 请及时联系运营商办理续费手续',
    ])

    text = '\n'.join(lines)
    return send_dingtalk_message(title, text)



def send_inspection_report(plan_name: str, exception_count: int, summary_lines: list[str]) -> bool:
    """发送巡检报告到钉钉"""
    if exception_count > 0:
        urgency = '⚠️ 异常' if exception_count > 5 else '📋 提醒'
        title = f'巡检报告 — {plan_name}'
    else:
        urgency = '✅ 正常'
        title = f'巡检报告 — {plan_name}'

    lines = [
        f'### {urgency} 巡检报告',
        '',
        f'- **方案**: {plan_name}',
        f'- **异常数**: {exception_count}',
        '',
    ]
    if summary_lines:
        lines.append('**异常摘要:**')
        lines.append('')
        for sl in summary_lines[:10]:
            lines.append(f'- {sl}')
    if exception_count == 0:
        lines.append('> 所有检查项正常')
    else:
        lines.append('')
        lines.append('> 请登录平台查看详细巡检报告')

    text = '\n'.join(lines)
    return send_dingtalk_message(title, text)


def send_test_message() -> bool:
    """发送测试消息"""
    return send_dingtalk_message(
        '测试通知',
        '### 测试通知\n\n这是一条来自内网运维平台的测试消息，如果您收到此消息说明钉钉 Webhook 配置正确。',
    )
