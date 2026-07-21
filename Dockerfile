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
# writable cache locations (some hosts run the container as a non-root user
# with a read-only home) and quieter TensorFlow logs
ENV KERAS_HOME=/tmp/keras \
    XDG_CACHE_HOME=/tmp/cache \
    MPLCONFIGDIR=/tmp/mpl \
    TF_CPP_MIN_LOG_LEVEL=2 \
    PYTHONUNBUFFERED=1
# opencv runtime libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY backend/ .
# the compiled frontend is served by Flask from ./static
COPY --from=frontend /fe/dist ./static
EXPOSE 5000
# bind to $PORT when the host provides one (Render, Cloud Run), else 5000
CMD gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 1 --timeout 120 app:app
