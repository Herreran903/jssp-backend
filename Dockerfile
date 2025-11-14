# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies including MiniZinc
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install MiniZinc
# Using the official MiniZinc release for Linux
RUN wget -q https://github.com/MiniZinc/MiniZincIDE/releases/download/2.8.5/MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz \
    && tar -xzf MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz -C /opt \
    && rm MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz \
    && ln -s /opt/MiniZincIDE-2.8.5-bundle-linux-x86_64/bin/minizinc /usr/local/bin/minizinc

# Verify MiniZinc installation
RUN minizinc --version

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Create storage directory for instances (optional)
RUN mkdir -p storage/instances

# Expose port (Render will set PORT env variable)
EXPOSE 8000

# Use PORT environment variable from Render, default to 8000
ENV PORT=8000

# Run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT