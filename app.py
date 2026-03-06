"""
AI Centers - Dashboard Backend
FastAPI backend для клиентской панели
"""

import os
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
from collections import defaultdict
from time import time

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite


app = FastAPI(title="AI Centers Dashboard")

# CORS для конкретных доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aicenters.co",
        "https://www.aicenters.co",
        "https://aicenters.netlify.app",
        "http://localhost:3000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Rate limiting для /api/chat
rate_limit_store = defaultdict(list)
RATE_LIMIT_MAX = 30  # запросов
RATE_LIMIT_WINDOW = 60  # секунд

# Шаблоны и статика
BASE_DIR = Path(__file__).parent
templates_dir = BASE_DIR / "templates"
static_dir = BASE_DIR / "static"
templates_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# === Chat API Proxy (for client widgets) ===
import aiohttp

GEMINI_API_KEY_CHAT = os.getenv("GEMINI_API_KEY", "")

def check_rate_limit(ip: str) -> bool:
    """Проверка rate limit: max 30 запросов в минуту с одного IP"""
    now = time()
    # Очищаем старые записи
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] if now - t < RATE_LIMIT_WINDOW]
    # Проверяем лимит
    if len(rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        return False
    # Добавляем текущий запрос
    rate_limit_store[ip].append(now)
    return True

@app.post("/api/chat")
async def chat_proxy(request: Request):
    """Chat API для клиентских виджетов — проксирует Gemini с rate limiting."""
    
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        return JSONResponse(
            {"error": "too_many_requests", "retry_after": 60},
            status_code=429
        )
    
    try:
        data = await request.json()
        user_message = data.get("message", "")
        language = data.get("language", "ru")
        
        if not user_message:
            return JSONResponse({"error": "empty message"}, status_code=400)
        
        if not GEMINI_API_KEY_CHAT:
            return JSONResponse({"error": "api_key_not_configured"}, status_code=500)
        
        system_prompt = """You are AI Centers sales assistant on the website aicenters.co.
Your job: answer questions about AI Centers platform and convert visitors into customers.

About AI Centers:
- Platform that creates AI bots/assistants for businesses
- Telegram bots, website chat widgets, voice AI secretaries
- 10+ niches: restaurants, salons, delivery, hotels, clinics, etc.
- Pricing: Starter $15/mo, Business $49/mo, Pro $99/mo, Enterprise $149/mo
- Voice AI Secretary: $299/mo (answers phone calls 24/7)
- Custom bot development: $499-999 one-time

Key benefits:
- Works 24/7, never sleeps
- Speaks 7 languages (RU, EN, GE, TR, KZ, UZ, AR)
- Answers in 2 seconds
- Saves 70% on staff costs
- Free demo available: @aicenters_demo_bot on Telegram

Rules:
- Be friendly, concise (2-3 sentences)
- Detect user language automatically and respond in same language
- Guide to demo bot or contact @aicenters_hub_bot for purchase
- Don't use markdown, plain text only"""
        
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.7}
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY_CHAT}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                result = await resp.json()
                reply = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Sorry, try again.")
                return JSONResponse({"reply": reply})
    except Exception as e:
        import logging
        logging.error(f"Chat proxy error: {e}")
        return JSONResponse({"error": "internal error"}, status_code=500)

# Конфигурация
BOT_TOKEN = os.getenv("ONBOARDING_BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ai_centers_bot")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/database/ai_centers.db")
PLATFORM_API_URL = os.getenv("PLATFORM_API_URL", "https://platform-api-production-f313.up.railway.app")

# Telegram Login Widget secret
TELEGRAM_SECRET = hashlib.sha256(BOT_TOKEN.encode()).digest()


# === Models ===

class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class BotConfig(BaseModel):
    business_name: str
    niche: str
    services: List[Dict[str, str]]
    schedule: str
    address: str
    phone: str
    language: str = "ru"


class StatsResponse(BaseModel):
    total_messages: int
    today_messages: int
    week_messages: int
    month_messages: int
    unique_users: int


class Conversation(BaseModel):
    id: int
    user_id: int
    username: str
    message: str
    response: str
    timestamp: str


# === Database ===

async def init_db():
    """Инициализация базы данных"""
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Таблица клиентов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                bot_token TEXT,
                config JSON,
                subscription_status TEXT DEFAULT 'trial',
                subscription_ends_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица сообщений (логи ботов)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                user_id INTEGER,
                username TEXT,
                message TEXT,
                response TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(telegram_id)
            )
        """)
        
        # Таблица статистики
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                date TEXT,
                messages_count INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients(telegram_id)
            )
        """)
        
        # CRM — лиды и заявки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                business TEXT,
                niche TEXT,
                contact TEXT,
                phone TEXT,
                address TEXT,
                schedule TEXT,
                services TEXT,
                description TEXT,
                plan TEXT,
                telegram_id INTEGER,
                username TEXT,
                status TEXT DEFAULT 'new',
                source TEXT DEFAULT 'telegram',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Оплаты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                plan TEXT,
                amount_stars INTEGER,
                status TEXT DEFAULT 'completed',
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Боты пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                bot_name TEXT,
                bot_username TEXT,
                business_name TEXT,
                niche TEXT,
                description TEXT,
                website_url TEXT,
                services JSON,
                bot_token TEXT,
                status TEXT DEFAULT 'creating',
                platform_bot_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(telegram_id)
            )
        """)
        
        # Партнёрская программа
        await db.execute("""
            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                partner_id TEXT UNIQUE,
                total_referrals INTEGER DEFAULT 0,
                active_referrals INTEGER DEFAULT 0,
                total_earnings REAL DEFAULT 0,
                balance_to_payout REAL DEFAULT 0,
                commission_rate REAL DEFAULT 0.20,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Рефералы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_id TEXT,
                client_id INTEGER,
                signup_date TEXT DEFAULT CURRENT_TIMESTAMP,
                first_payment_date TEXT,
                status TEXT DEFAULT 'pending',
                lifetime_value REAL DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients(telegram_id)
            )
        """)
        
        # Выплаты партнёрам
        await db.execute("""
            CREATE TABLE IF NOT EXISTS partner_payouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_id TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                paid_at TEXT,
                payment_method TEXT,
                transaction_id TEXT
            )
        """)
        
        await db.commit()


@app.on_event("startup")
async def startup():
    try:
        await init_db()
    except Exception as e:
        import logging
        logging.error(f"DB init failed: {e}")


# === Auth ===

def verify_telegram_auth(data: Dict) -> bool:
    """Проверка подлинности данных от Telegram Login Widget"""
    check_hash = data.pop("hash", None)
    if not check_hash:
        return False
    
    data_check_arr = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    hash_check = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash_check == check_hash


async def get_current_user(request: Request) -> Optional[int]:
    """Получение текущего пользователя из сессии"""
    # В продакшене использовать JWT или сессии
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    # Простая проверка: Bearer <telegram_id>
    try:
        telegram_id = int(auth_header.replace("Bearer ", ""))
        return telegram_id
    except:
        return None


# === Routes ===

@app.get("/health")
async def health_check():
    """Health check endpoint для мониторинга"""
    return {"status": "ok", "service": "ai-centers-dashboard"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "bot_username": BOT_USERNAME
    })


@app.post("/api/auth/telegram")
async def telegram_auth(user: TelegramUser):
    """Авторизация через Telegram"""
    
    # Проверяем подлинность данных
    user_data = user.dict()
    if not verify_telegram_auth(user_data):
        raise HTTPException(status_code=401, detail="Invalid authentication data")
    
    # Проверяем, что данные не старые (не более 1 часа)
    if datetime.now().timestamp() - user.auth_date > 3600:
        raise HTTPException(status_code=401, detail="Authentication data is too old")
    
    # Сохраняем/обновляем пользователя
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO clients (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
        """, (user.id, user.username, user.first_name, user.last_name))
        await db.commit()
    
    # Возвращаем токен (в продакшене использовать JWT)
    return {
        "access_token": str(user.id),
        "user": user.dict()
    }


@app.get("/api/config")
async def get_config(client_id: int = Depends(get_current_user)):
    """Получение конфигурации бота"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT config FROM clients WHERE telegram_id = ?",
            (client_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row or not row[0]:
                raise HTTPException(status_code=404, detail="Config not found")
            
            return json.loads(row[0])


@app.put("/api/config")
async def update_config(config: BotConfig, client_id: int = Depends(get_current_user)):
    """Обновление конфигурации бота"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE clients SET config = ? WHERE telegram_id = ?",
            (json.dumps(config.dict()), client_id)
        )
        await db.commit()
    
    return {"status": "updated"}


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(client_id: int = Depends(get_current_user)):
    """Получение статистики"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    now = datetime.now()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Всего сообщений
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE client_id = ?",
            (client_id,)
        ) as cursor:
            total_messages = (await cursor.fetchone())[0]
        
        # За сегодня
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE client_id = ? AND date(timestamp) = ?",
            (client_id, str(today))
        ) as cursor:
            today_messages = (await cursor.fetchone())[0]
        
        # За неделю
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE client_id = ? AND date(timestamp) >= ?",
            (client_id, str(week_ago))
        ) as cursor:
            week_messages = (await cursor.fetchone())[0]
        
        # За месяц
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE client_id = ? AND date(timestamp) >= ?",
            (client_id, str(month_ago))
        ) as cursor:
            month_messages = (await cursor.fetchone())[0]
        
        # Уникальные пользователи
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE client_id = ?",
            (client_id,)
        ) as cursor:
            unique_users = (await cursor.fetchone())[0]
    
    return StatsResponse(
        total_messages=total_messages,
        today_messages=today_messages,
        week_messages=week_messages,
        month_messages=month_messages,
        unique_users=unique_users
    )


@app.get("/api/conversations")
async def get_conversations(
    limit: int = 20,
    offset: int = 0,
    client_id: int = Depends(get_current_user)
):
    """Получение последних диалогов"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """SELECT id, user_id, username, message, response, timestamp
               FROM messages
               WHERE client_id = ?
               ORDER BY timestamp DESC
               LIMIT ? OFFSET ?""",
            (client_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            
            conversations = [
                Conversation(
                    id=row[0],
                    user_id=row[1],
                    username=row[2] or "unknown",
                    message=row[3],
                    response=row[4],
                    timestamp=row[5]
                )
                for row in rows
            ]
            
            return conversations


@app.get("/api/subscription")
async def get_subscription(client_id: int = Depends(get_current_user)):
    """Получение информации о подписке"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT subscription_status, subscription_ends_at FROM clients WHERE telegram_id = ?",
            (client_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "status": row[0] or "trial",
                "ends_at": row[1],
                "is_active": True  # TODO: проверка даты окончания
            }


# === Webhook для получения логов от ботов ===

@app.post("/api/webhook/message")
async def webhook_message(data: Dict):
    """
    Вебхук для получения логов сообщений от ботов
    
    Формат:
    {
        "client_id": 123456,
        "user_id": 789012,
        "username": "user123",
        "message": "Вопрос клиента",
        "response": "Ответ бота"
    }
    """
    
    required_fields = ["client_id", "user_id", "message", "response"]
    if not all(field in data for field in required_fields):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO messages (client_id, user_id, username, message, response)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["client_id"],
                data["user_id"],
                data.get("username", "unknown"),
                data["message"],
                data["response"]
            )
        )
        await db.commit()
    
    return {"status": "ok"}


# === CRM API ===

@app.post("/api/leads")
async def create_lead(data: Dict):
    """Создание лида из продажника или сайта"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO leads (name, business, niche, contact, phone, address, 
               schedule, services, description, plan, telegram_id, username, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", ""),
                data.get("business", ""),
                data.get("niche", ""),
                data.get("contact", ""),
                data.get("phone", ""),
                data.get("address", ""),
                data.get("schedule", ""),
                json.dumps(data.get("services", []), ensure_ascii=False),
                data.get("description", ""),
                data.get("plan", ""),
                data.get("telegram_id", 0),
                data.get("username", ""),
                data.get("source", "telegram")
            )
        )
        await db.commit()
    return {"status": "ok"}


@app.get("/api/leads")
async def get_leads():
    """Получение всех лидов (для админа)"""
    owner_id = int(os.getenv("OWNER_CHAT_ID", "5309206282"))
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT 100"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


@app.post("/api/payments")
async def record_payment(data: Dict):
    """Запись оплаты"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO payments (telegram_id, plan, amount_stars, status, payload)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data.get("telegram_id", 0),
                data.get("plan", ""),
                data.get("amount_stars", 0),
                data.get("status", "completed"),
                data.get("payload", "")
            )
        )
        await db.commit()
    return {"status": "ok"}


@app.get("/api/payments")
async def get_payments():
    """Получение всех оплат"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments ORDER BY created_at DESC LIMIT 100"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# === BOT CREATION API ===

class BotCreationRequest(BaseModel):
    business_name: str
    niche: str
    description: str
    website_url: Optional[str] = None
    services: List[Dict[str, str]]


class AutoBotRequest(BaseModel):
    text: str
    business_type: str
    language: str = "ru"


@app.post("/api/bots/create")
async def create_bot(bot_request: BotCreationRequest, client_id: int = Depends(get_current_user)):
    """Создание нового бота через platform-api"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Сохраняем в БД со статусом 'creating'
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO user_bots (client_id, business_name, niche, description, 
               website_url, services, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                bot_request.business_name,
                bot_request.niche,
                bot_request.description,
                bot_request.website_url,
                json.dumps(bot_request.services, ensure_ascii=False),
                'creating'
            )
        )
        bot_id = cursor.lastrowid
        await db.commit()
    
    # Отправляем запрос на platform-api
    try:
        platform_payload = {
            "business_name": bot_request.business_name,
            "niche": bot_request.niche,
            "description": bot_request.description,
            "website_url": bot_request.website_url,
            "services": bot_request.services,
            "client_telegram_id": client_id,
            "dashboard_bot_id": bot_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{PLATFORM_API_URL}/bots/auto-setup",
                json=platform_payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Обновляем статус в БД
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute(
                            """UPDATE user_bots SET status = 'processing', 
                               platform_bot_id = ? WHERE id = ?""",
                            (result.get("bot_id"), bot_id)
                        )
                        await db.commit()
                    
                    return {"bot_id": bot_id, "status": "processing", "platform_result": result}
                else:
                    # Обновляем статус как ошибка
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute(
                            "UPDATE user_bots SET status = 'error' WHERE id = ?",
                            (bot_id,)
                        )
                        await db.commit()
                    
                    raise HTTPException(status_code=500, detail="Platform API error")
                    
    except Exception as e:
        # Обновляем статус как ошибка
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE user_bots SET status = 'error' WHERE id = ?",
                (bot_id,)
            )
            await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Bot creation failed: {str(e)}")


@app.post("/api/bots/auto-setup")
async def auto_setup_bot(auto_request: AutoBotRequest, request: Request):
    """Проксирует запрос на Platform API для автоматического создания бота"""
    
    # Получаем user_id из заголовка X-User-Id
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    
    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id format")
    
    # Сохраняем заявку в БД
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO user_bots (client_id, business_name, niche, description, status) 
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                "Auto Bot",  # Временное название
                auto_request.business_type,
                auto_request.text[:500],  # Обрезаем описание
                'creating'
            )
        )
        bot_id = cursor.lastrowid
        await db.commit()
    
    # Проксируем запрос на Platform API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{PLATFORM_API_URL}/bots/auto-setup",
                json={
                    "text": auto_request.text,
                    "business_type": auto_request.business_type,
                    "language": auto_request.language,
                    "client_telegram_id": user_id,
                    "dashboard_bot_id": bot_id
                },
                headers={"X-User-Id": str(user_id)},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Обновляем статус в БД
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        await db.execute(
                            """UPDATE user_bots SET status = 'processing', 
                               platform_bot_id = ? WHERE id = ?""",
                            (result.get("bot_id"), bot_id)
                        )
                        await db.commit()
                    
                    return {
                        "success": True, 
                        "bot_id": bot_id,
                        "message": "Бот создаётся, это займёт 1-2 минуты",
                        "platform_result": result
                    }
                else:
                    error_text = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=f"Platform API error: {error_text}")
                    
    except aiohttp.ClientTimeout:
        # Обновляем статус как ошибка
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE user_bots SET status = 'error' WHERE id = ?",
                (bot_id,)
            )
            await db.commit()
        
        raise HTTPException(status_code=504, detail="Platform API timeout")
    
    except Exception as e:
        # Обновляем статус как ошибка
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE user_bots SET status = 'error' WHERE id = ?",
                (bot_id,)
            )
            await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Auto setup failed: {str(e)}")


@app.get("/api/bots")
async def get_user_bots(client_id: int = Depends(get_current_user)):
    """Получение ботов пользователя"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_bots WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            
            bots = []
            for row in rows:
                bot_dict = dict(row)
                if bot_dict['services']:
                    try:
                        bot_dict['services'] = json.loads(bot_dict['services'])
                    except:
                        bot_dict['services'] = []
                bots.append(bot_dict)
            
            return bots


@app.get("/api/bots/{bot_id}/status")
async def get_bot_status(bot_id: int, client_id: int = Depends(get_current_user)):
    """Проверка статуса создания бота"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT * FROM user_bots WHERE id = ? AND client_id = ?",
            (bot_id, client_id)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Bot not found")
            
            return {
                "id": row[0],
                "status": row[9],  # status column
                "bot_username": row[2],  # bot_username
                "platform_bot_id": row[10]  # platform_bot_id
            }


# === PARTNER PROGRAM API ===

@app.get("/api/partner/info")
async def get_partner_info(client_id: int = Depends(get_current_user)):
    """Получение информации о партнёре"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Получаем или создаём партнёра
        async with db.execute(
            "SELECT * FROM partners WHERE telegram_id = ?",
            (client_id,)
        ) as cursor:
            partner = await cursor.fetchone()
        
        if not partner:
            # Создаём нового партнёра
            import secrets
            partner_id = f"P{client_id}_{secrets.token_hex(4).upper()}"
            
            await db.execute(
                """INSERT INTO partners (telegram_id, partner_id) 
                   VALUES (?, ?)""",
                (client_id, partner_id)
            )
            await db.commit()
            
            # Получаем созданного партнёра
            async with db.execute(
                "SELECT * FROM partners WHERE telegram_id = ?",
                (client_id,)
            ) as cursor:
                partner = await cursor.fetchone()
        
        # Получаем рефералов
        async with db.execute(
            """SELECT r.*, c.first_name, c.username 
               FROM referrals r 
               LEFT JOIN clients c ON r.client_id = c.telegram_id 
               WHERE r.partner_id = ?
               ORDER BY r.signup_date DESC""",
            (partner[2],)  # partner_id
        ) as cursor:
            referrals = await cursor.fetchall()
        
        # Рассчитываем комиссию по уровням
        total_refs = partner[3]  # total_referrals
        if total_refs >= 21:
            commission_rate = 0.50
        elif total_refs >= 6:
            commission_rate = 0.35
        else:
            commission_rate = 0.20
        
        # Обновляем ставку комиссии если изменилась
        if commission_rate != partner[7]:  # commission_rate
            await db.execute(
                "UPDATE partners SET commission_rate = ? WHERE telegram_id = ?",
                (commission_rate, client_id)
            )
            await db.commit()
        
        return {
            "partner_id": partner[2],  # partner_id
            "referral_link": f"https://aicenters.co?ref={partner[2]}",
            "total_referrals": partner[3],  # total_referrals
            "active_referrals": partner[4],  # active_referrals
            "total_earnings": partner[5],  # total_earnings
            "balance_to_payout": partner[6],  # balance_to_payout
            "commission_rate": commission_rate,
            "commission_level": "50%" if total_refs >= 21 else "35%" if total_refs >= 6 else "20%",
            "referrals": [
                {
                    "client_id": r[2],
                    "client_name": r[9] or f"@{r[10]}" if r[10] else f"User {r[2]}",
                    "signup_date": r[3],
                    "first_payment_date": r[4],
                    "status": r[5],
                    "lifetime_value": r[6]
                }
                for r in referrals
            ]
        }


@app.post("/api/partner/payout")
async def request_payout(data: Dict, client_id: int = Depends(get_current_user)):
    """Запрос выплаты"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    amount = data.get("amount", 0)
    if amount < 50:  # Минимальная выплата $50
        raise HTTPException(status_code=400, detail="Minimum payout is $50")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем баланс партнёра
        async with db.execute(
            "SELECT partner_id, balance_to_payout FROM partners WHERE telegram_id = ?",
            (client_id,)
        ) as cursor:
            partner = await cursor.fetchone()
        
        if not partner or partner[1] < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Создаём заявку на выплату
        await db.execute(
            """INSERT INTO partner_payouts (partner_id, amount, payment_method) 
               VALUES (?, ?, ?)""",
            (partner[0], amount, data.get("payment_method", "bank"))
        )
        
        # Уменьшаем баланс
        await db.execute(
            """UPDATE partners SET balance_to_payout = balance_to_payout - ? 
               WHERE telegram_id = ?""",
            (amount, client_id)
        )
        
        await db.commit()
    
    # Уведомляем админа о заявке (здесь можно отправить в Telegram)
    # TODO: send notification to admin
    
    return {"status": "requested", "amount": amount}


@app.get("/api/partner/payouts")
async def get_partner_payouts(client_id: int = Depends(get_current_user)):
    """История выплат партнёра"""
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Получаем partner_id
        async with db.execute(
            "SELECT partner_id FROM partners WHERE telegram_id = ?",
            (client_id,)
        ) as cursor:
            result = await cursor.fetchone()
            
            if not result:
                return []
        
        partner_id = result[0]
        
        # Получаем выплаты
        async with db.execute(
            "SELECT * FROM partner_payouts WHERE partner_id = ? ORDER BY requested_at DESC",
            (partner_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "amount": row[2],
                    "status": row[3],
                    "requested_at": row[4],
                    "paid_at": row[5],
                    "payment_method": row[6]
                }
                for row in rows
            ]


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", 8000))
    logging.info(f"Starting dashboard on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")