from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import secrets, asyncio
from datetime import datetime, timedelta
import os
from pymongo import MongoClient

# --------------------------
# Config
# --------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# MongoDB setup
mongo = MongoClient(MONGO_DB_URI)
db = mongo.g4f
premium_users = db.premium_users
api_keys = db.api_keys

# FastAPI init
app = FastAPI(title="G4F API Bot")

# Pyrogram client
pyro_app = Client("g4f-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
# Pyrogram Handlers
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Help", callback_data="help")]])
    await message.reply_text(
        "👋 Welcome to G4F Bot!\n\n"
        "Premium users can generate API keys to use the G4F API.\n"
        "Use the buttons below for help.",
        reply_markup=keyboard
    )

@pyro_app.on_callback_query(filters.regex("help"))
async def help_button(client, callback_query):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])
    await callback_query.message.edit_text(
        "📚 **Help:**\n"
        "- `/genkey` → Generate API key (Premium only)\n"
        "- `/chat` → Chat via bot\n"
        "Press Back to return.",
        reply_markup=keyboard
    )

@pyro_app.on_callback_query(filters.regex("back"))
async def back_button(client, callback_query):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Help", callback_data="help")]])
    await callback_query.message.edit_text(
        "👋 Welcome to G4F Bot!\n\nUse the buttons below for help.",
        reply_markup=keyboard
    )

# --------------------------
# Owner Endpoint: Give Premium
# --------------------------
@app.post("/give_premium")
def give_premium(req: GivePremiumRequest, request: Request):
    telegram_user_id = int(request.headers.get("X-TG-ID", 0))
    if telegram_user_id != OWNER_ID:
        raise HTTPException(status_code=403, detail="Only owner can give premium")
    premium_users.update_one({"user_id": req.user_id}, {"$set": {"premium": True}}, upsert=True)
    return {"status": "success", "user_id": req.user_id, "message": "Premium granted"}

# --------------------------
# Create API Key (Premium Only)
# --------------------------
@app.post("/create_key")
def create_key(req: KeyRequest, request: Request):
    telegram_user_id = int(request.headers.get("X-TG-ID", 0))
    if not premium_users.find_one({"user_id": telegram_user_id, "premium": True}):
        raise HTTPException(status_code=403, detail="Only premium users can generate API key")
    key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=30)
    api_keys.insert_one({"key": key, "username": req.username, "expires_at": expires_at})
    return {"api_key": key, "expires_at": expires_at.isoformat()}

# --------------------------
# Generate Message Endpoint
# --------------------------
@app.post("/g4f/generate")
async def generate(req: GenerateRequest, request: Request):
    api_key = request.headers.get("X-API-Key")
    key_data = api_keys.find_one({"key": api_key})
    if not key_data:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    if datetime.utcnow() > key_data["expires_at"]:
        raise HTTPException(status_code=403, detail="API key expired")
    
    chat_id = req.chat_id
    prompt = req.prompt
    start_msg = await pyro_app.send_message(chat_id, "**✨ Processing your request...**")
    
    try:
        await pyro_app.send_message(chat_id, prompt)
        await pyro_app.edit_message_text(chat_id, start_msg.id, "✅ Message sent successfully!")
        return {"status": "success", "sent": prompt, "to": chat_id}
    except Exception as e:
        await pyro_app.edit_message_text(chat_id, start_msg.id, f"❌ Failed: {e}")
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
