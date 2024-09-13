FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "scraper.py"]
