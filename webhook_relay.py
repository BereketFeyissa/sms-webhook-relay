# relay.py
from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel
import httpx
import os
import logging
import re
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

KANEL_URL = os.getenv("KANEL_URL", "")
KANEL_USER = os.getenv("KANEL_USER", "")
KANEL_PASS = os.getenv("KANEL_PASS", "")
KANEL_SENDER = os.getenv("KANEL_SENDER", "")
DEFAULT_RECIPIENT = os.getenv("SMS_TO", "")

# Optional: restrict with a custom secret
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

class Alert(BaseModel):
    status: str  # 'firing' or 'resolved'
    labels: Dict[str, str]
    annotations: Dict[str, str]

class GrafanaWebhookPayload(BaseModel):
    status: str  # Overall status
    alerts: List[Alert]
    title: Optional[str] = None
    message: Optional[str] = None

@app.get("/health")
async def health_check():
    return {"status": "ok"}

def extract_useful_info(error_message: str) -> str:
    """Extract only the most useful information from error messages."""
    if not error_message:
        return "Alert triggered"
    
    # Remove Grafana-specific prefixes
    error_message = re.sub(r'^\[sse\.dataQueryError\]\s*', '', error_message)
    error_message = re.sub(r'^\[.*?\]\s*', '', error_message)
    
    # Extract connection errors more cleanly
    if 'connection refused' in error_message.lower():
        # Try to extract the host and port
        match = re.search(r'dial tcp ([\d\.]+):(\d+):', error_message)
        if match:
            host, port = match.groups()
            return f"Connection refused to {host}:{port}"
    
    # For HTTP errors, simplify
    if 'Post "' in error_message:
        # Extract URL from Post requests
        match = re.search(r'Post "([^"]+)"', error_message)
        if match:
            url = match.group(1)
            # Simplify URL if it's long
            if len(url) > 40:
                # Keep only the hostname and port
                url_parts = url.split('/')
                if len(url_parts) >= 3:
                    url = url_parts[2]  # Keep just the hostname:port
            return f"Failed to connect to {url}"
    
    # Return error message truncated to reasonable length
    if len(error_message) > 100:
        return error_message[:97] + "..."
    
    return error_message

def format_alert_message(alert: Alert) -> str:
    """Format alert message with visual indicators and useful info."""
    alert_name = alert.labels.get("alertname", "Unknown Alert")
    
    # Get the most relevant annotation field
    error_field = alert.annotations.get("Error") or alert.annotations.get("error")
    summary_field = alert.annotations.get("summary") or alert.annotations.get("description")
    
    # Use error field if available, otherwise summary
    if error_field:
        message_content = extract_useful_info(error_field)
    elif summary_field:
        message_content = summary_field
    else:
        # Try to extract from common annotations
        for key, value in alert.annotations.items():
            if key.lower() not in ['summary', 'description', 'grafana_state_reason']:
                message_content = extract_useful_info(value)
                break
        else:
            message_content = "Alert condition met"
    
    # Add visual indicators based on status
    if alert.status == "firing":
        # 🔥 for firing alerts
        prefix = "🔥 "
        status_text = "ALERT"
    elif alert.status == "resolved":
        # ✅ for resolved alerts
        prefix = "✅ "
        status_text = "RESOLVED"
    else:
        prefix = "⚠️ "
        status_text = alert.status.upper()
    
    # Format the final message
    message = f"{prefix}{status_text}: {alert_name}"
    
    # Add message content if it's not too long
    if message_content and len(message_content) < 50:
        message += f" - {message_content}"
    elif message_content:
        # If content is long, put it on next line
        message += f"\n{message_content}"
    
    # Add instance/endpoint if available
    instance = alert.labels.get("instance") or alert.labels.get("endpoint")
    if instance:
        # Simplify long URLs
        if len(instance) > 30:
            # Extract just the hostname
            if "://" in instance:
                instance = instance.split("://")[1]
            if "/" in instance:
                instance = instance.split("/")[0]
        message += f"\n📍 {instance}"
    
    return message

@app.post("/webhook/sms")
async def handle_webhook(request: Request, 
                         x_webhook_token: str = Header(default="")):
    
    if WEBHOOK_SECRET and x_webhook_token != WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook access attempt.")
        raise HTTPException(status_code=403, detail="Unauthorized webhook access")

    try:
        payload_json = await request.json()
        logger.info(f"Received webhook with status: {payload_json.get('status', 'unknown')}")
        payload = GrafanaWebhookPayload(**payload_json)
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {e}")

    # Track if we sent any SMS
    sms_sent = 0
    
    async with httpx.AsyncClient(verify=False) as client:
        for alert in payload.alerts:
            # Format the alert message with visual indicators
            message = format_alert_message(alert)
            
            # Optional: Get phone number dynamically from alert labels
            to_number = alert.labels.get("phone", DEFAULT_RECIPIENT)
            
            if not to_number:
                logger.warning(f"No phone number for alert: {alert.labels.get('alertname')}")
                continue

            # Truncate message for SMS limits
            # SMS limits: 160 chars for GSM, 70 for Unicode (emojis are Unicode)
            # Count emojis as 2 chars each
            emoji_count = message.count('🔥') + message.count('✅') + message.count('⚠️') + message.count('📍')
            adjusted_length = len(message) + emoji_count  # Emojis count as 2 chars in SMS
            
            if adjusted_length > 140:
                # Truncate carefully, preserving emojis if possible
                if '🔥' in message or '✅' in message:
                    # Keep the emoji prefix
                    prefix_end = message.find(' ') + 1
                    prefix = message[:prefix_end]
                    rest = message[prefix_end:]
                    if len(rest) > (135 - len(prefix)):
                        rest = rest[:132 - len(prefix)] + "..."
                    message = prefix + rest
                else:
                    message = message[:137] + "..."

            params = {
                "username": KANEL_USER,
                "password": KANEL_PASS,
                "coding": "2",  # Unicode for emojis
                "charset": "utf-8",
                "from": KANEL_SENDER,
                "to": to_number,
                "text": message
            }

            try:
                logger.info(f"Sending {alert.status} SMS to {to_number}")
                response = await client.get(KANEL_URL, params=params)
                response.raise_for_status()
                logger.info(f"Successfully sent SMS to {to_number}. Response: {response.text}")
                sms_sent += 1
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error sending SMS to {to_number}: {e.response.status_code} - {e.response.text}")
                # Do not raise HTTPException here to allow processing other alerts
            except httpx.RequestError as e:
                logger.error(f"Request error sending SMS to {to_number}: {e}")
    
    return {"status": "Webhook processed", "sms_sent": sms_sent}