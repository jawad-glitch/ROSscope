#!/usr/bin/env python3
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import config

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class SlackNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send(self, alert):
        if not REQUESTS_AVAILABLE:
            print("[ROSscope] requests library not installed — Slack notifications disabled")
            return

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "ROSscope Anomaly Alert"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Topic:*\n{alert['topic']}"},
                        {"type": "mrkdwn", "text": f"*Z-Score:*\n{alert['z_score']}"},
                        {"type": "mrkdwn", "text": f"*State:*\n{alert['state']}"},
                        {"type": "mrkdwn", "text": f"*Fired At:*\n{alert['fired_at']}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "→ <http://localhost:8001|View in ROSscope>"
                    }
                }
            ]
        }

        try:
            response = requests.post(self.webhook_url, json=message, timeout=5)
            if response.status_code == 200:
                print(f"[ROSscope] Slack notification sent for {alert['topic']}")
            else:
                print(f"[ROSscope] Slack notification failed: {response.status_code}")
        except Exception as e:
            print(f"[ROSscope] Slack notification error: {e}")


class EmailNotifier:
    def __init__(self, smtp_host, smtp_port, sender, recipients):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = recipients

    def send(self, alert):
        if not self.recipients:
            return

        subject = f"ROSscope Alert — {alert['topic']} anomaly detected"
        body = f"""
ROSscope Anomaly Alert

Topic:    {alert['topic']}
Z-Score:  {alert['z_score']}
State:    {alert['state']}
Fired At: {alert['fired_at']}

View in ROSscope: http://localhost:8001

This alert was fired automatically by ROSscope anomaly detection.
To resolve this alert, visit the Alerts page in ROSscope.
        """.strip()

        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = ', '.join(self.recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.sendmail(self.sender, self.recipients, msg.as_string())
            print(f"[ROSscope] Email notification sent for {alert['topic']}")
        except Exception as e:
            print(f"[ROSscope] Email notification error: {e}")


class NotificationManager:
    def __init__(self, config):
        self.notifiers = []

        # Slack
        slack_cfg = config.alerts.get('slack', {})
        if slack_cfg.get('enabled') and slack_cfg.get('webhook_url'):
            self.notifiers.append(SlackNotifier(slack_cfg['webhook_url']))
            print("[ROSscope] Slack notifications enabled")

        # Email
        email_cfg = config.alerts.get('email', {})
        if email_cfg.get('enabled') and email_cfg.get('recipients'):
            self.notifiers.append(EmailNotifier(
                smtp_host=email_cfg.get('smtp_host', ''),
                smtp_port=email_cfg.get('smtp_port', 587),
                sender=email_cfg.get('sender', ''),
                recipients=email_cfg.get('recipients', [])
            ))
            print("[ROSscope] Email notifications enabled")

        if not self.notifiers:
            print("[ROSscope] No notification channels configured")

    def notify(self, alert):
        """Send notification to all configured channels in background threads."""
        for notifier in self.notifiers:
            thread = threading.Thread(
                target=notifier.send,
                args=(alert,),
                daemon=True
            )
            thread.start()

notification_manager = NotificationManager(config)