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
app = FastAPI(title="G4F MongoDB Bot")

# Pyrogram client
pyro_app = Client("g4f-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --------------------------
# Pyrogram Bot Commands
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Help", callback_data="help")]])
    await message.reply_text(
        "👋 Welcome to Espro Api Bot!\n\n"
        "Premium users can generate API keys to use the Espro Api.\n"
        "Use the buttons below for help.",
        reply_markup=keyboard
    )

@pyro_app.on_callback_query(filters.regex("help"))
async def help_button(client, callback_query):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])
    await callback_query.message.edit_text(
        "📚 **Help:**\n"
        "- `/genkey` → Generate API key (Premium only)\n"
        "- `/givepremium <user_id>` → Owner can give premium\n"
        "- `/chat` → Chat via bot\n"
        "Press Back to return.",
        reply_markup=keyboard
    )

@pyro_app.on_callback_query(filters.regex("back"))
async def back_button(client, callback_query):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Help", callback_data="help")]])
    await callback_query.message.edit_text(
        "👋 Welcome to Espro Api Bot!\n\nUse the buttons below for help.",
        reply_markup=keyboard
    )

# --------------------------
# Owner gives premium via bot
# --------------------------
@pyro_app.on_message(filters.command("givepremium") & filters.user(OWNER_ID))
async def give_premium(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /givepremium <user_id>")
        return
    user_id = int(message.command[1])
    premium_users.update_one({"user_id": user_id}, {"$set": {"premium": True}}, upsert=True)
    await message.reply_text(f"✅ User {user_id} has been granted premium.")

# --------------------------
# Premium user generates API key via bot
# --------------------------
@pyro_app.on_message(filters.command("genkey"))
async def generate_key(client, message: Message):
    user_id = message.from_user.id
    if not premium_users.find_one({"user_id": user_id, "premium": True}):
        await message.reply_text("❌ You are not a premium user.")
        return
    key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=30)
    api_keys.insert_one({"key": key, "user_id": user_id, "expires_at": expires_at})
    await message.reply_text(f"🔑 Your API key:\n`{key}`\nValid until {expires_at}")

# --------------------------
# Request Models
# --------------------------
class GenerateRequest(BaseModel):
    prompt: str
    chat_id: int

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
