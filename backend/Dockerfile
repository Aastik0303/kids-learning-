# The API image. Build context is `backend/`.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first so a code change does not reinstall the world.
COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . /app
RUN chmod +x /app/start.sh

# Render (and most hosts) hand the port in $PORT; 8008 is the local default.
ENV PORT=8008
EXPOSE 8008

CMD ["/app/start.sh"]
