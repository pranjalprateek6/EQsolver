FROM python:3.12-slim

WORKDIR /app

# opencv runtime libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt is a pinned lockfile (see requirements.in)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", \
     "--worker-class", "gthread", "--timeout", "30", "--access-logfile", "-", "app:app"]
