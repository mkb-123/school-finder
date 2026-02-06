# ---- Stage 1: Build frontend ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install Python dependencies (production only)
RUN uv sync --frozen --no-dev

# Copy frontend build from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy database directly (no volume mount needed since DB is in git)
RUN mkdir -p /app/data
COPY data/schools.db /app/data/schools.db

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/councils')" || exit 1

# Seed on first boot, then start the app
CMD ["./entrypoint.sh"]
