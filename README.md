# 🤖 AI Centers - Dashboard

Панель управления для клиентов платформы AI Centers. Позволяет управлять настройками AI-бота, просматривать статистику и диалоги.

## 🎯 Возможности

- ✅ **Авторизация через Telegram** - безопасный вход через Telegram Login Widget
- 📊 **Статистика в реальном времени** - сообщения за день/неделю/месяц, уникальные пользователи
- 💬 **История диалогов** - последние 20 диалогов с клиентами
- ⚙️ **Редактирование настроек** - услуги, цены, расписание, контакты
- 💳 **Статус подписки** - отображение текущего статуса и даты окончания

## 🛠 Технологии

- **Backend**: FastAPI + Python 3.11
- **Database**: SQLite (aiosqlite)
- **Frontend**: Vanilla JS + CSS
- **Templates**: Jinja2
- **Auth**: Telegram Login Widget

## 📋 Требования

- Python 3.11+
- Docker (для деплоя)
- Telegram Bot Token

## 🚀 Запуск локально

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
export ONBOARDING_BOT_TOKEN="your_bot_token"
export BOT_USERNAME="your_bot_username"
export DATABASE_PATH="./database/ai_centers.db"
```

### 3. Запуск приложения

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: `http://localhost:8000`

## 🐳 Деплой с Docker

### Локальная сборка и запуск

```bash
# Сборка образа
docker build -t ai-centers-dashboard .

# Запуск контейнера
docker run -d \
  -p 8000:8000 \
  -e ONBOARDING_BOT_TOKEN="your_bot_token" \
  -e BOT_USERNAME="your_bot_username" \
  -e DATABASE_PATH="/app/database/ai_centers.db" \
  --name dashboard \
  ai-centers-dashboard
```

### Деплой на Railway

1. **Создайте проект в Railway**
   ```bash
   # Установите Railway CLI
   npm i -g @railway/cli
   
   # Войдите в аккаунт
   railway login
   
   # Создайте новый проект
   railway init
   ```

2. **Добавьте переменные окружения в Railway Dashboard**
   - `ONBOARDING_BOT_TOKEN` - токен вашего бота
   - `BOT_USERNAME` - username бота (без @)
   - `DATABASE_PATH` - `/app/database/ai_centers.db`
   - `PORT` - `8000` (автоматически устанавливается Railway)

3. **Деплой**
   ```bash
   railway up
   ```

4. **Получите URL**
   ```bash
   railway domain
   ```

### Деплой на Render

1. Создайте новый Web Service
2. Подключите этот GitHub репозиторий
3. Настройки:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Добавьте Environment Variables:
   - `ONBOARDING_BOT_TOKEN`
   - `BOT_USERNAME`
   - `DATABASE_PATH=/opt/render/project/src/database/ai_centers.db`

### Деплой на Fly.io

1. Установите Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Войдите и создайте приложение:
   ```bash
   fly auth login
   fly launch --no-deploy
   ```

3. Установите секреты:
   ```bash
   fly secrets set ONBOARDING_BOT_TOKEN="your_token"
   fly secrets set BOT_USERNAME="your_bot"
   ```

4. Деплой:
   ```bash
   fly deploy
   ```

## 📁 Структура проекта

```
dashboard/
├── app.py                 # FastAPI приложение
├── requirements.txt       # Python зависимости
├── Dockerfile            # Docker образ
├── README.md             # Документация
├── templates/
│   └── dashboard.html    # Главная страница
├── static/
│   ├── style.css        # Стили
│   └── script.js        # Frontend логика
└── database/
    └── ai_centers.db    # SQLite база (создается автоматически)
```

## 🔌 API Endpoints

### Авторизация

- `POST /api/auth/telegram` - авторизация через Telegram
  ```json
  {
    "id": 123456789,
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "auth_date": 1234567890,
    "hash": "..."
  }
  ```

### Данные

- `GET /api/stats` - статистика сообщений
- `GET /api/conversations?limit=20&offset=0` - список диалогов
- `GET /api/config` - настройки бота
- `PUT /api/config` - обновление настроек
- `GET /api/subscription` - информация о подписке

### Webhook

- `POST /api/webhook/message` - прием логов от ботов
  ```json
  {
    "client_id": 123456,
    "user_id": 789012,
    "username": "user123",
    "message": "Вопрос клиента",
    "response": "Ответ бота"
  }
  ```

## 🔐 Безопасность

- Авторизация через Telegram Login Widget с проверкой подписи
- CORS настроен для безопасного взаимодействия
- Все запросы к API требуют авторизации (Authorization: Bearer token)
- Проверка актуальности auth_date (не более 1 часа)

## 📊 База данных

### Схема

**clients** - клиенты платформы
- telegram_id (PK)
- username, first_name, last_name
- bot_token
- config (JSON)
- subscription_status, subscription_ends_at
- created_at

**messages** - логи диалогов
- id (PK)
- client_id (FK)
- user_id, username
- message, response
- timestamp

**stats** - агрегированная статистика
- id (PK)
- client_id (FK)
- date
- messages_count, unique_users

## 🔧 Настройка Telegram Login Widget

1. Получите Bot Token от [@BotFather](https://t.me/BotFather)
2. Установите домен для бота:
   ```
   /setdomain
   @your_bot
   yourdomain.com
   ```
3. Убедитесь, что BOT_USERNAME в переменных окружения совпадает с username бота

## 🐛 Troubleshooting

### Dashboard не загружается

- Проверьте логи: `docker logs dashboard`
- Убедитесь, что порт 8000 не занят
- Проверьте переменные окружения

### Telegram Login не работает

- Убедитесь, что домен настроен в @BotFather
- Проверьте BOT_USERNAME (без @)
- Проверьте ONBOARDING_BOT_TOKEN

### База данных не создается

- Проверьте права доступа к директории database/
- Проверьте DATABASE_PATH в переменных окружения

## 📝 Changelog

### v1.0.0 (2026-03-01)
- ✨ Первая версия
- 🔐 Авторизация через Telegram
- 📊 Статистика и диалоги
- ⚙️ Редактирование настроек
- 💳 Информация о подписке
- 🐳 Docker support

## 📄 License

MIT License - используйте свободно для своих проектов!

## 👨‍💻 Author

AI Centers Platform  
Telegram: [@tokazov](https://t.me/tokazov)

---

**Нужна помощь?** Создайте issue в GitHub или напишите в Telegram!
