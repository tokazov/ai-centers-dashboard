FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Создаем директорию для БД
RUN mkdir -p /app/database

# Переменные окружения (будут переопределены при запуске)
ENV DATABASE_PATH=/app/database/ai_centers.db
ENV ONBOARDING_BOT_TOKEN=""
ENV BOT_USERNAME="ai_centers_bot"
ENV PORT=8000

EXPOSE ${PORT}

CMD ["python", "app.py"]
