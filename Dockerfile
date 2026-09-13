FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY viewer ./viewer
COPY templates ./templates
COPY static ./static

RUN mkdir -p /app/data

EXPOSE 8081

CMD ["gunicorn", "--bind", "0.0.0.0:8081", "--workers", "2", "--threads", "2", "viewer.app:app"]
