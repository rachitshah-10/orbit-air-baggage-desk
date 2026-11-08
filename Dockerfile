# STRETCH GOAL 4
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir pytest ruff

COPY . .

CMD ["pytest"]
