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
app = FastAPI(title="Espro Telegram Bot API")

# --------------------------
# MongoDB Setup
# --------------------------
mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["espro_bot"]

# --------------------------
# Pyrogram Client
# --------------------------
pyro_app = Client(
    "espro-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --------------------------
# Safe Edit Function
# --------------------------
async def safe_edit_message(message, new_text, reply_markup=None):
    """Edit only if text is different to avoid MESSAGE_NOT_MODIFIED"""
    if message.text != new_text:
        await message.edit_text(new_text, reply_markup=reply_markup)

# --------------------------
# Startup & Shutdown
# --------------------------
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(pyro_app.start())

@app.on_event("shutdown")
async def shutdown_event():
    await pyro_app.stop()

# --------------------------
# /start Command (Detailed)
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"

    text = (
        f"👋 **Hello! Welcome to Espro API Bot**\n\n"
        f"**Your Status:** {premium_status}\n\n"
        "📌 **What I Can Do:**\n"
        "- Send messages to any chat via the API endpoint `/espro/generate`.\n"
        "- Premium users can generate their own 30-day API keys using `/genkey`.\n"
        "- Owner can grant premium to any user using `/givepremium <user_id>`.\n\n"
        "💡 **Instructions:**\n"
        "1. Check your premium status above.\n"
        "2. Use `/help` to learn more about available commands and API usage.\n"
        "3. Once you have an API key, you can start sending messages via the API.\n\n"
        "🔗 **Buttons below will help you navigate:**"
    )

    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")]
    ]

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --------------------------
# /help Command (Detailed)
# --------------------------
@pyro_app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    buttons = [
        [InlineKeyboardButton("Back", callback_data="back")]
    ]
    text = (
        "📚 **Bot Help**\n\n"
        "🔹 **Premium Users:** Can generate a 30-day API key using `/genkey`.\n"
        "🔹 **Owner:** Can give premium to users using `/givepremium <user_id>`.\n"
        "🔹 **Send Messages via API:** Use `/espro/generate` endpoint with your API key.\n\n"
        "💡 **Tips:**\n"
        "- Make sure to keep your API key secret.\n"
        "- API keys expire after 30 days.\n"
        "- Only premium users can generate keys."
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --------------------------
# Callback Query: Help & Back
# --------------------------
@pyro_app.on_callback_query(filters.regex("help"))
async def help_button(client, callback_query):
    buttons = [[InlineKeyboardButton("Back", callback_data="back")]]
    text = (
        "📚 **Bot Help**\n\n"
        "🔹 **Premium Users:** Can generate a 30-day API key using `/genkey`.\n"
        "🔹 **Owner:** Can give premium to users using `/givepremium <user_id>`.\n"
        "🔹 **Send Messages via API:** Use `/espro/generate` endpoint with your API key.\n\n"
        "💡 **Tips:**\n"
        "- Make sure to keep your API key secret.\n"
        "- API keys expire after 30 days.\n"
        "- Only premium users can generate keys."
    )
    await safe_edit_message(callback_query.message, text, InlineKeyboardMarkup(buttons))

@pyro_app.on_callback_query(filters.regex("back"))
async def back_button(client, callback_query):
    user_id = callback_query.from_user.id
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"
    buttons = [[InlineKeyboardButton("Help", callback_data="help")]]
    text = f"👋 Hello! I am your Espro API Bot.\nYour Status: {premium_status}"
    await safe_edit_message(callback_query.message, text, InlineKeyboardMarkup(buttons))

# --------------------------
# Owner: Give Premium Command
# --------------------------
@pyro_app.on_message(filters.command("givepremium") & filters.user(OWNER_ID))
async def give_premium_command(client: Client, message: Message):
    if len(message.command) != 2:
        await message.reply_text("Usage: /givepremium <user_id>")
        return
    try:
        user_id = int(message.command[1])
        await db.premium_users.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "granted_at": datetime.utcnow()}},
            upsert=True
        )
        await message.reply_text(f"✅ User `{user_id}` has been granted premium!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID.")

# --------------------------
# Premium User: Generate API Key (Auto Username)
# --------------------------
@pyro_app.on_message(filters.command("genkey"))
async def generate_api_key(client: Client, message: Message):
    user_id = message.from_user.id
    premium_user = await db.premium_users.find_one({"user_id": user_id})
    if not premium_user:
        await message.reply_text("❌ You are not a premium user.")
        return

    username = message.from_user.username or str(user_id)
    key = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(days=30)

    await db.api_keys.insert_one({
        "api_key": key,
        "username": username,
        "expires_at": expires_at
    })

    await message.reply_text(
        f"✅ API Key generated!\nKey: `{key}`\nValid until: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Associated username: `{username}`"
    )

# --------------------------
# FastAPI Endpoint: Send Message via API
# --------------------------
class GenerateRequest(BaseModel):
    prompt: str
    chat_id: int

@app.post("/espro/generate")
async def generate(req: GenerateRequest, request: Request):
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
