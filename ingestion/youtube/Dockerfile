FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /worker
COPY ingestion/youtube/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ingestion/youtube/worker.py .
CMD ["python", "worker.py"]
