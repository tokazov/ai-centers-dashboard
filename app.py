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

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite


app = FastAPI(title="AI Centers Dashboard")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/api/chat")
async def chat_proxy(request: Request):
    """Chat API для клиентских виджетов — проксирует Gemini."""
    try:
        data = await request.json()
        user_message = data.get("message", "")
        history = data.get("history", [])
        
        if not user_message:
            return JSONResponse({"error": "empty message"}, status_code=400)
        
        system_prompt = data.get("system_prompt",
            "You are a helpful AI assistant for a business. "
            "Answer concisely in the user's language. Be friendly.")
        
        contents = history[-10:] if history else []
        contents.append({"role": "user", "parts": [{"text": user_message}]})
        
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
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


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", 8000))
    logging.info(f"Starting dashboard on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
