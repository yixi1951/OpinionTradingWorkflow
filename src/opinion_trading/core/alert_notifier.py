from __future__ import annotations

import os
from typing import Dict

import requests


class AlertNotifier:
    """Push alerts to DingTalk / WeCom / Telegram when configured via env vars."""

    def __init__(self, timeout: int = 8) -> None:
        self.timeout = timeout
        self.dingtalk_webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
        self.wecom_webhook = os.environ.get("WECOM_WEBHOOK", "").strip()
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    def push_alert(self, alert: Dict) -> Dict:
        msg = self._format_message(alert)
        result = {
            "dingtalk": self._push_dingtalk(msg),
            "wecom": self._push_wecom(msg),
            "telegram": self._push_telegram(msg),
        }
        return result

    def _format_message(self, alert: Dict) -> str:
        return (
            "[OpinionTrading Alert]\n"
            f"symbol={alert.get('symbol', '')}\n"
            f"severity={alert.get('severity', '')}\n"
            f"direction={alert.get('direction', '')}\n"
            f"delta={float(alert.get('delta', 0.0)):.4f}\n"
            f"score={float(alert.get('previous_score', 0.0)):.4f} -> {float(alert.get('current_score', 0.0)):.4f}\n"
            f"time={alert.get('time', '')}"
        )

    def _push_dingtalk(self, message: str) -> Dict:
        if not self.dingtalk_webhook:
            return {"enabled": False, "ok": False, "detail": "DINGTALK_WEBHOOK not set"}
        try:
            payload = {"msgtype": "text", "text": {"content": message}}
            r = requests.post(self.dingtalk_webhook, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return {"enabled": True, "ok": True, "detail": "sent"}
        except Exception as e:
            return {"enabled": True, "ok": False, "detail": str(e)}

    def _push_wecom(self, message: str) -> Dict:
        if not self.wecom_webhook:
            return {"enabled": False, "ok": False, "detail": "WECOM_WEBHOOK not set"}
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": message.replace("\n", "\n> ")},
            }
            r = requests.post(self.wecom_webhook, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return {"enabled": True, "ok": True, "detail": "sent"}
        except Exception as e:
            return {"enabled": True, "ok": False, "detail": str(e)}

    def _push_telegram(self, message: str) -> Dict:
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return {
                "enabled": False,
                "ok": False,
                "detail": "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set",
            }
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {"chat_id": self.telegram_chat_id, "text": message}
            r = requests.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return {"enabled": True, "ok": True, "detail": "sent"}
        except Exception as e:
            return {"enabled": True, "ok": False, "detail": str(e)}
