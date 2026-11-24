# commuttify API + optional inline GTFS-RT worker (Render / any Docker host)
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

ENV PYTHONUNBUFFERED=1

# Render injects $PORT (default 10000)
EXPOSE 10000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
