# 🚀 AI Centers Dashboard - Deployment Guide

## ✅ Готово к деплою!

Репозиторий: **https://github.com/tokazov/ai-centers-dashboard**

---

## 📦 Что включено

### Основные файлы
- ✅ `app.py` - FastAPI backend (проверен, рабочий)
- ✅ `templates/dashboard.html` - UI с Telegram Login Widget
- ✅ `static/style.css` - стили
- ✅ `static/script.js` - frontend логика
- ✅ `requirements.txt` - Python зависимости
- ✅ `Dockerfile` - для Docker деплоя
- ✅ `README.md` - полная документация

### Конфигурации для платформ
- ✅ `fly.toml` - Fly.io
- ✅ `railway.toml` - Railway
- ✅ `render.yaml` - Render.com
- ✅ `.env.example` - шаблон переменных окружения
- ✅ `test_local.sh` - скрипт для локального тестирования

### Дополнительно
- ✅ `.gitignore` - исключения для Git
- ✅ `.dockerignore` - исключения для Docker
- ✅ Health check endpoint `/health`

---

## 🎯 Основные возможности Dashboard

### 🔐 Авторизация
- Telegram Login Widget с проверкой подписи
- Безопасная аутентификация через Telegram
- Сессии хранятся в localStorage

### 📊 Статистика
- Сообщения сегодня/за неделю/за месяц
- Уникальные пользователи
- Обновление в реальном времени

### 💬 Диалоги
- Последние 20 диалогов
- История вопросов и ответов бота
- Информация о пользователях

### ⚙️ Настройки
- Редактирование услуг и цен
- Расписание работы
- Контактная информация
- Динамическое добавление/удаление услуг

### 💳 Подписка
- Статус подписки (trial/active/expired)
- Дата окончания
- Визуальная индикация статуса

---

## 🚀 Быстрый старт

### 1. Локальный запуск

```bash
# Клонировать репозиторий
git clone https://github.com/tokazov/ai-centers-dashboard.git
cd ai-centers-dashboard

# Настроить переменные окружения
cp .env.example .env
# Отредактировать .env (добавить BOT_TOKEN и BOT_USERNAME)

# Запустить
./test_local.sh
```

### 2. Docker

```bash
docker build -t ai-centers-dashboard .
docker run -d \
  -p 8000:8000 \
  -e ONBOARDING_BOT_TOKEN="your_token" \
  -e BOT_USERNAME="your_bot" \
  --name dashboard \
  ai-centers-dashboard
```

### 3. Railway (рекомендуется)

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

Добавить в Railway Dashboard:
- `ONBOARDING_BOT_TOKEN`
- `BOT_USERNAME`
- `DATABASE_PATH=/app/database/ai_centers.db`

### 4. Fly.io

```bash
fly launch --no-deploy
fly secrets set ONBOARDING_BOT_TOKEN="your_token"
fly secrets set BOT_USERNAME="your_bot"
fly deploy
```

### 5. Render.com

1. Создать Web Service
2. Подключить GitHub репозиторий
3. Добавить переменные окружения
4. Deploy!

---

## 🔧 Необходимые переменные окружения

| Переменная | Описание | Пример |
|-----------|----------|---------|
| `ONBOARDING_BOT_TOKEN` | Токен бота от @BotFather | `123456:ABC-DEF...` |
| `BOT_USERNAME` | Username бота (без @) | `ai_centers_bot` |
| `DATABASE_PATH` | Путь к SQLite БД | `./database/ai_centers.db` |
| `PORT` | Порт сервера (опционально) | `8000` |

---

## 📡 API Endpoints

### Public
- `GET /` - главная страница (dashboard.html)
- `GET /health` - health check
- `POST /api/auth/telegram` - авторизация через Telegram

### Authenticated
- `GET /api/stats` - статистика сообщений
- `GET /api/conversations` - список диалогов
- `GET /api/config` - конфигурация бота
- `PUT /api/config` - обновление конфигурации
- `GET /api/subscription` - информация о подписке

### Webhooks
- `POST /api/webhook/message` - прием логов от ботов

---

## 🔐 Настройка Telegram Login Widget

1. Получить Bot Token от @BotFather
2. Установить домен для бота:
   ```
   /setdomain
   @your_bot
   yourdomain.com
   ```
3. Проверить, что `BOT_USERNAME` в переменных совпадает с username бота

---

## 📊 База данных

### Структура SQLite

**clients** - клиенты
- telegram_id, username, first_name, last_name
- bot_token, config (JSON)
- subscription_status, subscription_ends_at
- created_at

**messages** - логи диалогов
- id, client_id, user_id, username
- message, response
- timestamp

**stats** - агрегированная статистика
- id, client_id
- date, messages_count, unique_users

База создаётся автоматически при первом запуске.

---

## ✅ Проверка работоспособности

После деплоя проверьте:

1. **Health check**: `curl https://your-domain.com/health`
   - Ожидаемый ответ: `{"status":"ok","service":"ai-centers-dashboard"}`

2. **Главная страница**: откройте в браузере
   - Должна загрузиться страница авторизации
   - Виден Telegram Login Widget

3. **Авторизация**: нажмите "Log in via Telegram"
   - Откроется popup Telegram
   - После авторизации должен открыться dashboard

4. **API**: проверьте доступность endpoints
   ```bash
   # После авторизации получите token
   TOKEN="your_telegram_id"
   
   # Проверка stats
   curl -H "Authorization: Bearer $TOKEN" \
        https://your-domain.com/api/stats
   ```

---

## 🐛 Troubleshooting

### Dashboard не открывается
- Проверьте логи: `railway logs` / `fly logs` / `docker logs dashboard`
- Убедитесь что порт доступен
- Проверьте переменные окружения

### Telegram Login не работает
1. Проверьте домен в @BotFather (`/setdomain`)
2. Убедитесь что `BOT_USERNAME` без символа `@`
3. Проверьте что `ONBOARDING_BOT_TOKEN` корректный
4. Откройте консоль браузера (F12) - посмотрите ошибки

### База данных не создаётся
- Проверьте права доступа к директории
- Убедитесь что `DATABASE_PATH` указывает на доступную директорию
- Для cloud платформ используйте volume/disk

### API возвращает 401
- Токен авторизации истёк - перелогиньтесь
- Проверьте что передаёте заголовок `Authorization: Bearer <token>`

---

## 📝 Следующие шаги

После успешного деплоя:

1. **Настроить домен** (если нужно)
   - Railway: Settings → Domains → Add Custom Domain
   - Fly.io: `fly certs add yourdomain.com`
   - Render: Settings → Custom Domains

2. **Обновить домен в @BotFather**
   ```
   /setdomain
   @your_bot
   your-actual-domain.com
   ```

3. **Подключить ботов клиентов**
   - Каждый клиентский бот должен отправлять логи на `/api/webhook/message`
   - Формат: `{"client_id": 123, "user_id": 456, "message": "...", "response": "..."}`

4. **Мониторинг**
   - Настроить health check на `/health` endpoint
   - Настроить алерты на платформе деплоя

---

## 📞 Поддержка

- **GitHub**: https://github.com/tokazov/ai-centers-dashboard
- **Issues**: https://github.com/tokazov/ai-centers-dashboard/issues
- **Telegram**: @tokazov

---

**Готово к продакшену! 🚀**

*Version: 1.0.0*  
*Last updated: 2026-03-01*
