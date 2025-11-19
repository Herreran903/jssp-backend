# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps: compilación + GL/EGL/X11/fontconfig/gpg-error que suele pedir el bundle de MiniZinc
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    ca-certificates \
    # GL / EGL
    libgl1 \
    libegl1 \
    # X11 / render
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxrender1 \
    libxext6 \
    # fuentes y texto
    libfontconfig1 \
    libfreetype6 \
    # glib / errores gpg (arrastrados por algunas libs gráficas)
    libglib2.0-0 \
    libgpg-error0 \
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
