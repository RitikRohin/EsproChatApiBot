import os
import secrets
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --------------------------
# Config
# --------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# --------------------------
# FastAPI Init
# --------------------------
app = FastAPI(title="G4F Telegram Bot API")

# --------------------------
# MongoDB Setup
# --------------------------
mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["g4f_bot"]

# --------------------------
# Pyrogram Client (Memory-safe)
# --------------------------
pyro_app = Client(
    "g4f-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True  # Memory session, SQLite-free
)

# --------------------------
# Pyrogram Commands with Help Button
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"

    # Only Help button
    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")]
    ]

    await message.reply_text(
        f"👋 Hello! I am your G4F API Bot.\nYour Status: {premium_status}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@pyro_app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    user_id = message.from_user.id
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"

    # Only Help button
    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")]
    ]

    await message.reply_text(
        f"📚 Bot Help\nYour Status: {premium_status}\nUse /create_key endpoint to generate API key (Premium Only).",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --------------------------
# Callback for Help Button
# --------------------------
@pyro_app.on_callback_query(filters.regex("help"))
async def help_button(client, callback_query):
    await callback_query.answer(
        "Use /create_key to generate your API Key (Premium Only).\n"
        "Use /g4f/generate to send messages via API.",
        show_alert=True
    )

# --------------------------
# Request Models
# --------------------------
class KeyRequest(BaseModel):
    username: str

class GenerateRequest(BaseModel):
    prompt: str
    chat_id: int

class GivePremiumRequest(BaseModel):
    user_id: int

# --------------------------
# Helper: Cleanup Expired API Keys
# --------------------------
async def cleanup_expired_keys():
    await db.api_keys.delete_many({"expires_at": {"$lt": datetime.utcnow()}})

# --------------------------
# Owner Endpoint: Give Premium
# --------------------------
@app.post("/give_premium")
async def give_premium(req: GivePremiumRequest, request: Request):
    telegram_user_id = request.headers.get("X-TG-ID")
    if not telegram_user_id or int(telegram_user_id) != OWNER_ID:
        raise HTTPException(status_code=403, detail="Only owner can give premium")
    await db.premium_users.update_one(
        {"user_id": req.user_id},
        {"$set": {"user_id": req.user_id}},
        upsert=True
    )
    return {"status": "success", "user_id": req.user_id, "message": "Premium granted"}

# --------------------------
# Create API Key (Premium Only)
# --------------------------
@app.post("/create_key")
async def create_key(req: KeyRequest, request: Request):
    await cleanup_expired_keys()
    telegram_user_id = request.headers.get("X-TG-ID")
    if not telegram_user_id:
        raise HTTPException(status_code=403, detail="Missing X-TG-ID header")
    premium_user = await db.premium_users.find_one({"user_id": int(telegram_user_id)})
    if not premium_user:
        raise HTTPException(status_code=403, detail="Only premium users can generate API key")
    key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=30)
    await db.api_keys.insert_one({
        "api_key": key,
        "username": req.username,
        "expires_at": expires_at
    })
    return {"api_key": key, "expires_at": expires_at.isoformat()}

# --------------------------
# Generate Message via Bot
# --------------------------
@app.post("/g4f/generate")
async def generate(req: GenerateRequest, request: Request):
    await cleanup_expired_keys()
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    key_doc = await db.api_keys.find_one({"api_key": api_key})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    if datetime.utcnow() > key_doc["expires_at"]:
        raise HTTPException(status_code=403, detail="API Key expired")
    
    chat_id = req.chat_id
    prompt = req.prompt
    start_message_id = None
    try:
        start_msg = await pyro_app.send_message(chat_id, "**✨ Processing your request...**")
        start_message_id = start_msg.id
        await pyro_app.send_message(chat_id, prompt)
        await pyro_app.edit_message_text(
            chat_id,
            start_message_id,
            "✅ **Message sent successfully.**"
        )
        return {"status": "success", "sent": prompt, "to": chat_id}
    except Exception as e:
        if start_message_id:
            await pyro_app.edit_message_text(chat_id, start_message_id, f"❌ Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --------------------------
# Startup & Shutdown
# --------------------------
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(pyro_app.start())

@app.on_event("shutdown")
async def shutdown_event():
    await pyro_app.stop()
