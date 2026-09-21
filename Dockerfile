FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
# HF Spaces runs the container as UID 1000 — create matching user (harmless on Render/VPS too)
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
RUN mkdir -p downloads && chmod 777 downloads
USER user
EXPOSE 8000
EXPOSE 7860
# Render injects $PORT — use it, fallback 8000 for local/VPS.
# Web-only on free hosts (bot polling wastes the 512MB RAM; run bot.py locally instead).
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-${WEB_PORT:-8000}}"]
