FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
# Added build-essential for NeMo components that might need compilation
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    make \
    espeak-ng \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install packages with increased timeout and retries
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout=1000 --retries=5 -r requirements.txt

# Pre-download gruut data
RUN python3 -m gruut download en-us

# Pre-download NeMo model to avoid slow first-run and redundant downloads
# We set a cache directory to ensure it stays in the image
ENV NEMO_CACHE_DIR=/app/.cache/nemo
RUN mkdir -p $NEMO_CACHE_DIR
RUN python3 -c "from nemo.collections.asr.models import ASRModel; ASRModel.from_pretrained('nvidia/parakeet-tdt-0.6b-v3')"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NEMO_CACHE_DIR=/app/.cache/nemo

COPY app.py .
COPY templates ./templates

EXPOSE 9022

# Using gunicorn for production
CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "app:app", "--bind", "0.0.0.0:9022", "--timeout", "300"]
