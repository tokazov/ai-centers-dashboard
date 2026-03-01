# AI Centers Dashboard - Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для базы данных
RUN mkdir -p /app/database

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Запуск приложения
CMD uvicorn app:app --host 0.0.0.0 --port $PORT
