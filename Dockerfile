FROM node:24-alpine AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-trixie AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 sgancia && useradd --uid 10001 --gid sgancia --create-home sgancia
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY --chown=sgancia:sgancia backend/ ./
COPY --from=frontend --chown=sgancia:sgancia /web/dist/ ./static/
USER sgancia
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${SGANCIA_TRUSTED_PROXIES:-127.0.0.1}\""]

# Optional verification image; the default production target remains free of test tools.
FROM runtime AS test
USER root
COPY backend/requirements-dev.lock ./requirements-dev.lock
RUN pip install --no-cache-dir -r requirements-dev.lock && chown sgancia:sgancia /app
USER sgancia
CMD ["python", "-m", "pytest", "-q"]

FROM runtime AS production
