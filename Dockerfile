FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Render injects $PORT — use it, fallback 8000 for local/VPS.
# Web-only on free hosts (bot polling wastes the 512MB RAM; run bot.py locally instead).
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-${WEB_PORT:-8000}}"]
