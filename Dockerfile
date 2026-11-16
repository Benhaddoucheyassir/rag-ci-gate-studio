# Stage 1: Build frontend
FROM node:20-slim AS builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + static serving
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn

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

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
