FROM python:3.11-slim

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# Install minimal system dependencies and install Python packages
COPY requirements.txt ./
RUN apt-get update && \
	apt-get install -y --no-install-recommends ca-certificates && \
	pip install --no-cache-dir --upgrade pip && \
	pip install --no-cache-dir -r requirements.txt && \
	apt-get purge -y --auto-remove && \
	rm -rf /var/lib/apt/lists/* /root/.cache/pip

# Copy the project files and set ownership to the non-root user
COPY --chown=app:app . /app

USER app

EXPOSE 8000

CMD ["uvicorn", "webhook_relay:app", "--host", "0.0.0.0", "--port", "8000"]
