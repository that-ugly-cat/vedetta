FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

RUN mkdir -p data srtm_tiles

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8006"]
