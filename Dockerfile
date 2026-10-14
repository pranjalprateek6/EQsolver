# Single-service production image: build the frontend, then serve it and the
# API together from Flask/gunicorn on one port. Build from the repo root:
#   docker build -t eqsolver .
#   docker run -p 5000:5000 eqsolver   # open http://localhost:5000
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
# writable cache location (some hosts run the container as a non-root user
# with a read-only home)
ENV XDG_CACHE_HOME=/tmp/cache \
    PYTHONUNBUFFERED=1
# opencv runtime libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# requirements.txt is a pinned lockfile (see requirements.in)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# the compiled frontend is served by Flask from ./static
COPY --from=frontend /fe/dist ./static
# run as an unprivileged user
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 5000
# Bind to $PORT when the host provides one (Render, Cloud Run), else 5000.
# Threads keep other requests moving while one waits on a solve; SymPy runs
# in separate killable processes (sandbox.py), so no request outlives
# SOLVE_TIMEOUT there. Raise WEB_CONCURRENCY for more worker processes on
# hosts with more memory than the free tier's 512 MB.
CMD gunicorn --bind "0.0.0.0:${PORT:-5000}" \
    --workers "${WEB_CONCURRENCY:-1}" --threads "${GUNICORN_THREADS:-4}" \
    --worker-class gthread --timeout 30 --graceful-timeout 10 \
    --access-logfile - app:app
