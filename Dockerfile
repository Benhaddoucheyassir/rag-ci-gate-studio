# Stage 1: Build frontend
FROM node:20-slim AS builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + uv + static serving
FROM python:3.11-slim
WORKDIR /app

# Copy uv from astral-sh
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies with uv (ultra-fast, low RAM)
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY corpus/ ./corpus/
COPY benchmark/ ./benchmark/
COPY scripts/ ./scripts/
COPY rag_pipeline.py ./
COPY conftest.py ./

# Copy built frontend from Stage 1
COPY --from=builder /app/frontend/dist ./frontend/dist

# Create non-root user 1000 and assign ownership
RUN useradd -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
