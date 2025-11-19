# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps: compilación + MiniZinc + libs GL/EGL/fontconfig que pide fzn-gecode
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    ca-certificates \
    libgl1 \
    libegl1 \
    libfontconfig1 \
  && rm -rf /var/lib/apt/lists/*

# Install MiniZinc
RUN wget -q https://github.com/MiniZinc/MiniZincIDE/releases/download/2.8.5/MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz \
    && tar -xzf MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz -C /opt \
    && rm MiniZincIDE-2.8.5-bundle-linux-x86_64.tgz \
    && ln -s /opt/MiniZincIDE-2.8.5-bundle-linux-x86_64/bin/minizinc /usr/local/bin/minizinc

# Verify MiniZinc installation
RUN minizinc --version

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN mkdir -p storage/instances

EXPOSE 8000
ENV PORT=8000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
