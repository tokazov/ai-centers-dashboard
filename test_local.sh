#!/bin/bash
# Скрипт для локального тестирования Dashboard

echo "🚀 AI Centers Dashboard - Local Test"
echo "======================================"

# Проверка зависимостей
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

echo "✅ Python3 найден: $(python3 --version)"

# Создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

echo "🔧 Активация venv и установка зависимостей..."
source venv/bin/activate
pip install -q -r requirements.txt

# Проверка .env
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе .env.example"
    echo "   cp .env.example .env"
    echo "   Затем заполните переменные окружения."
    exit 1
fi

echo "✅ Загрузка переменных окружения из .env"
export $(cat .env | xargs)

# Создание директории для БД
mkdir -p database

echo ""
echo "🎯 Запуск сервера..."
echo "   URL: http://localhost:8000"
echo "   Нажмите Ctrl+C для остановки"
echo ""

uvicorn app:app --reload --host 0.0.0.0 --port 8000
