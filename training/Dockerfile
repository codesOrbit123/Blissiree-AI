FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY training/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY training/train.py /app/train.py
COPY training/data /app/data
CMD ["python", "/app/train.py"]
