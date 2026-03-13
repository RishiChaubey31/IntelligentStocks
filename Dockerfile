FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True)"

COPY backend/ backend/
COPY .env* ./

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/data

EXPOSE 8001

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001}"
