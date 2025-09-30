from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from pyrogram import Client, filters
from pyrogram.types import Message
import secrets
import asyncio
from datetime import datetime, timedelta
import os
import json

# --------------------------
# Config
# --------------------------
API_ID = int(os.getenv("API_ID", "1234567"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
PREMIUM_FILE = "premium_users.json"
API_KEYS_FILE = "api_keys.json"

# --------------------------
# FastAPI Init
# --------------------------
app = FastAPI(title="G4F Telegram Bot API")

# --------------------------
# Load / Save Helpers
# --------------------------
def load_premium_users():
    if os.path.exists(PREMIUM_FILE):
        with open(PREMIUM_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_premium_users():
    with open(PREMIUM_FILE, "w") as f:
        json.dump(list(premium_users), f)

def load_api_keys():
    if os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE, "r") as f:
            raw = json.load(f)
            return {k: {"username": v["username"], "expires_at": datetime.fromisoformat(v["expires_at"])} for k,v in raw.items()}
    return {}

def save_api_keys():
    with open(API_KEYS_FILE, "w") as f:
        raw = {k: {"username": v["username"], "expires_at": v["expires_at"].isoformat()} for k,v in api_keys.items()}
        json.dump(raw, f)

# --------------------------
# Memory Stores
# --------------------------
premium_users = load_premium_users()
api_keys = load_api_keys()

# --------------------------
# Pyrogram Client
# --------------------------
pyro_app = Client(
    "g4f-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --------------------------
# Pyrogram Command Handlers
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text(
        "👋 Hello! I am your API Bot.\n"
        "Premium users can generate API keys and send messages via API."
    )

@pyro_app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    is_premium = user_id in premium_users
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"
    await message.reply_text(
        f"📚 Bot Help\n\nYour Status: {premium_status}\n"
        "Use /key endpoint to generate API key (Premium Only).\n"
        
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
def cleanup_expired_keys():
    now = datetime.utcnow()
    expired = [k for k,v in api_keys.items() if v["expires_at"] < now]
    for k in expired:
        del api_keys[k]
    if expired:
        save_api_keys()

# --------------------------
# Owner Endpoint: Give Premium
# --------------------------
@app.post("/premium")
def give_premium(req: GivePremiumRequest, request: Request):
    telegram_user_id = request.headers.get("X-TG-ID")
    if not telegram_user_id or int(telegram_user_id) != OWNER_ID:
        raise HTTPException(status_code=403, detail="Only owner can give premium")
    premium_users.add(req.user_id)
    save_premium_users()
    return {"status": "success", "user_id": req.user_id, "message": "Premium granted"}

# --------------------------
# Create API Key (Premium Only)
# --------------------------
@app.post("/key")
def create_key(req: KeyRequest, request: Request):
    cleanup_expired_keys()
    telegram_user_id = request.headers.get("X-TG-ID")
    if not telegram_user_id or int(telegram_user_id) not in premium_users:
        raise HTTPException(status_code=403, detail="Only premium users can generate API key")
    key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=30)
    api_keys[key] = {"username": req.username, "expires_at": expires_at}
    save_api_keys()
    return {"api_key": key, "expires_at": expires_at.isoformat()}

# --------------------------
# Generate Message via Bot
# --------------------------
@app.post("/g4f/generate")
async def generate(req: GenerateRequest, request: Request):
    cleanup_expired_keys()
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key not in api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    key_data = api_keys[api_key]
    if datetime.utcnow() > key_data["expires_at"]:
        raise HTTPException(status_code=403, detail="API key expired")
    chat_id = req.chat_id
    prompt = req.prompt
    start_message_id = None
    try:
        start_message = await pyro_app.send_message(chat_id, "**✨ Your request is being processed...**")
        start_message_id = start_message.id
        await pyro_app.send_message(chat_id, prompt)
        await pyro_app.edit_message_text(
            chat_id,
            start_message_id,
            "✅ **Message sent successfully.**\nContact support at @ur_haiwan"
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
