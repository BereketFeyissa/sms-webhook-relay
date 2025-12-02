# SMS Webhook Relay

A small FastAPI app that receives Grafana (or similar) webhook alert payloads and relays them as SMS messages via a Kanel-compatible SMS gateway.

Files:
- `webhook_relay.py` - FastAPI application.
- `requirements.txt` - runtime dependencies for production image.
- `Dockerfile` - multi-stage Dockerfile to build and run the app.
- `.env.example` - example environment variables.

Quick start (local)

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set required environment variables (see `.env.example`) or export them:

```bash
export KANEL_URL="https://your-kanel-endpoint/send"
export KANEL_USER="username"
export KANEL_PASS="password"
export KANEL_SENDER="SENDERNAME"
export SMS_TO="+2519xxxxxxx"
export WEBHOOK_SECRET="optional-secret"
```

3. Run locally using `uvicorn`:

```bash
uvicorn webhook_relay:app --host 0.0.0.0 --port 8000
```

4. Health check:

```bash
curl http://localhost:8000/health
# => {"status":"ok"}
```

Running in Docker

Build the image:

```bash
docker build -t sms-webhook-relay:latest .
```

Run the container (example):

```bash
docker run --env-file .env \
  -p 8000:8000 \
  sms-webhook-relay:latest
```

Environment variables

Use `.env` or export these variables before running the container or app:

- `KANEL_URL` - The Kanel SMS gateway request URL (e.g. `https://kanel.example/send`).
- `KANEL_USER` - Username for the SMS gateway.
- `KANEL_PASS` - Password for the SMS gateway.
- `KANEL_SENDER` - Sender ID (from field) used when sending SMS.
- `SMS_TO` - Default recipient phone number used when alert doesn't include one.
- `WEBHOOK_SECRET` - Optional secret header to protect the webhook endpoint. When set, the request must include header `x-webhook-token` with the same value.

Notes

- TLS verification: outgoing requests use system CA certificates by default. For development you can disable verification by setting `DISABLE_TLS_VERIFY=true` in your environment (not recommended for production).
- Alerts are expected to follow Grafana's webhook format with an `alerts` array containing `labels` and `annotations` objects.

Continuous Integration

This repository includes a GitHub Actions workflow to run tests on push and pull requests to `main`.

Local tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

