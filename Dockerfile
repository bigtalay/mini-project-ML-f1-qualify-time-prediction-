FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /workspace
COPY requirements.lock ./
RUN python -m pip install -r requirements.lock
COPY f1_project/ ./f1_project/
COPY --from=frontend /build/dist ./frontend/dist
WORKDIR /workspace/f1_project
EXPOSE 8501
CMD ["uvicorn", "intelligence.api:app", "--host", "0.0.0.0", "--port", "8501"]
