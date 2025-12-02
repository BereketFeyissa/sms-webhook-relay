# webhook_relay.py
from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel
import httpx
import os
import logging
from typing import List, Dict

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
    labels: Dict[str, str]
    annotations: Dict[str, str]

class GrafanaWebhookPayload(BaseModel):
    alerts: List[Alert]

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/webhook/sms")
async def handle_webhook(request: Request, 
                         x_webhook_token: str = Header(default="")):
    
    if WEBHOOK_SECRET and x_webhook_token != WEBHOOK_SECRET:
        logger.warning("Unauthorized webhook access attempt.")
        raise HTTPException(status_code=403, detail="Unauthorized webhook access")

    try:
        payload_json = await request.json()
        logger.info(f"Received webhook payload: {payload_json}")
        payload = GrafanaWebhookPayload(**payload_json)
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {e}")

    async with httpx.AsyncClient(verify=False) as client:
        for alert in payload.alerts:
            # Extract message
            message = alert.annotations.get("summary", "No summary provided.")
            
            # Optional: Get phone number dynamically from alert labels
            to_number = alert.labels.get("phone", DEFAULT_RECIPIENT)

            params = {
                "username": KANEL_USER,
                "password": KANEL_PASS,
                "coding": "2",
                "charset": "utf-8",
                "from": KANEL_SENDER,
                "to": to_number,
                "text": message
            }

            try:
                logger.info(f"Sending SMS to {to_number}")
                response = await client.get(KANEL_URL, params=params)
                response.raise_for_status()
                logger.info(f"Successfully sent SMS to {to_number}. Response: {response.text}")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error sending SMS to {to_number}: {e.response.status_code} - {e.response.text}")
                # Do not raise HTTPException here to allow processing other alerts
            except httpx.RequestError as e:
                logger.error(f"Request error sending SMS to {to_number}: {e}")
    
    return {"status": "Webhook processed"}
