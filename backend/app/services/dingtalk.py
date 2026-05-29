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
    renewal_cycle: str = 'annual',
    renewal_cost: Optional[float] = None,
    annual_cost: Optional[float] = None,
) -> bool:
    """发送宽带续费提醒"""
    urgency = '⚠️ 紧急' if days_remaining <= 7 else '📋 提醒'
    cycle_label = RENEWAL_CYCLE_LABELS.get(renewal_cycle, '每年')
    title = f'宽带续费提醒'

    lines = [
        f'### {urgency} 宽带续费提醒',
        '',
        f'- **运营商**: {provider}',
    ]
    if circuit_id:
        lines.append(f'- **线路编号**: {circuit_id}')
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
        f'- **到期日期**: {contract_end.strftime("%Y-%m-%d")}',
        f'- **剩余天数**: **{days_remaining} 天**',
    ])
    if contact_name:
        lines.append(f'- **联系人**: {contact_name}')

    lines.extend([
        '',
        '> 请及时联系运营商办理续费手续',
    ])

    text = '\n'.join(lines)
    return send_dingtalk_message(title, text)


def send_test_message() -> bool:
    """发送测试消息"""
    return send_dingtalk_message(
        '测试通知',
        '### 测试通知\n\n这是一条来自内网运维平台的测试消息，如果您收到此消息说明钉钉 Webhook 配置正确。',
    )
