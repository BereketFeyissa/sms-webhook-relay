# Stage 1: Build the virtual environment with dependencies
FROM python:3.13.9-alpine3.21 AS builder

# Set working directory
WORKDIR /app

# Create a virtual environment
RUN python -m venv /opt/venv

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Create the final, lean production image
FROM python:3.13.9-alpine3.21

# Set working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code
COPY webhook_relay.py .

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Expose the port the app will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "webhook_relay:app", "--host", "0.0.0.0", "--port", "8000"]
