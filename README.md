# AI Centers Dashboard

Панель управления для AI-ботов клиентов.

## Возможности

- 🔐 Авторизация через Telegram Login Widget
- 📊 Статистика сообщений и пользователей
- 💬 Просмотр диалогов с клиентами
- ⚙️ Настройка параметров бота (название, услуги, расписание)
- 💳 Управление подпиской

## Технологии

- **FastAPI** — бэкенд API
- **Jinja2** — шаблоны HTML
- **SQLite** (aiosqlite) — база данных
- **Vanilla JS** — фронтенд (без фреймворков)

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
# Локально
uvicorn app:app --reload

# Через Docker
docker build -t ai-centers-dashboard .
docker run -p 8000:8000 \
  -e ONBOARDING_BOT_TOKEN="your_bot_token" \
  -e BOT_USERNAME="your_bot_username" \
  ai-centers-dashboard
```

## Переменные окружения

- `ONBOARDING_BOT_TOKEN` — токен Telegram-бота (для проверки авторизации)
- `BOT_USERNAME` — username бота (для виджета логина)
- `DATABASE_PATH` — путь к SQLite БД (default: `../database/ai_centers.db`)
- `PORT` — порт для uvicorn (default: 8000)

## API Endpoints

### Публичные
- `GET /` — главная страница (HTML)
- `POST /api/auth/telegram` — авторизация через Telegram
- `GET /health` — health check

### Защищенные (требуют Bearer token)
- `GET /api/config` — получить конфиг бота
- `PUT /api/config` — обновить конфиг
- `GET /api/stats` — статистика
- `GET /api/conversations` — последние диалоги
- `GET /api/subscription` — информация о подписке

### Webhooks
- `POST /api/webhook/message` — прием логов от ботов клиентов

## Структура

```
dashboard/
├── app.py              # FastAPI приложение
├── templates/
│   └── dashboard.html  # Главная страница
├── static/
│   ├── style.css       # Стили
│   └── script.js       # Клиентская логика
├── requirements.txt
├── Dockerfile
└── README.md
```

## Deploy

### Railway / Render
1. Подключить GitHub repo
2. Установить переменные окружения
3. Команда старта: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Vercel (serverless)
Не подходит из-за SQLite и WebSockets. Используйте Railway или VPS.
