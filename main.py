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
    in_memory=True
)

# --------------------------
# Startup & Shutdown
# --------------------------
@app.on_event("startup")
async def startup_event():
    # Start the Pyrogram client in the background
    asyncio.create_task(pyro_app.start())

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the Pyrogram client
    await pyro_app.stop()

# --------------------------
# Pyrogram Commands
# --------------------------
@pyro_app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    # Check premium status
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"

    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")]
    ]

    await message.reply_text(
        f"👋 Hello! I am your G4F API Bot.\nYour Status: **{premium_status}**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@pyro_app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    buttons = [
        [InlineKeyboardButton("Back", callback_data="back")]
    ]
    await message.reply_text(
        "📚 **Bot Help**\n\n"
        "- **Premium** users can generate API key using `/genkey`.\n"
        "- **Owner** can give premium using `/givepremium <user_id>`.\n"
        "- Use the `/g4f/generate` API endpoint to send messages.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --------------------------
# Callback Query: Help & Back
# --------------------------
@pyro_app.on_callback_query(filters.regex("help"))
async def help_button(client, callback_query):
    buttons = [
        [InlineKeyboardButton("Back", callback_data="back")]
    ]
    await callback_query.message.edit_text(
        "📚 **Bot Help**\n\n"
        "- **Premium** users can generate API key using `/genkey`.\n"
        "- **Owner** can give premium using `/givepremium <user_id>`.\n"
        "- Use the `/g4f/generate` API endpoint to send messages.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@pyro_app.on_callback_query(filters.regex("back"))
async def back_button(client, callback_query):
    user_id = callback_query.from_user.id
    is_premium = await db.premium_users.find_one({"user_id": user_id})
    premium_status = "✅ Premium" if is_premium else "❌ Non-Premium"

    buttons = [
        [InlineKeyboardButton("Help", callback_data="help")]
    ]

    await callback_query.message.edit_text(
        f"👋 Hello! I am your G4F API Bot.\nYour Status: **{premium_status}**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

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
        # Insert or update user in premium_users collection
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
    # Check if user is premium
    premium_user = await db.premium_users.find_one({"user_id": user_id})
    if not premium_user:
        await message.reply_text("❌ You are not a premium user.")
        return

    # Use username or user ID if username is not set
    username = message.from_user.username or str(user_id)
    key = secrets.token_hex(16)  # Generate 32-character hex key
    expires_at = datetime.utcnow() + timedelta(days=30) # Key expires in 30 days

    # Store the new API key
    await db.api_keys.insert_one({
        "api_key": key,
        "username": username,
        "expires_at": expires_at
    })

    await message.reply_text(
        f"✅ API Key generated!\nKey: `{key}`\nValid until: `{expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
        f"Associated user: `{username}`"
    )

# --------------------------
# FastAPI Endpoints (API Key Use)
# --------------------------

class GenerateRequest(BaseModel):
    """Pydantic model for the API request body."""
    prompt: str
    chat_id: int

@app.post("/g4f/generate")
async def generate(req: GenerateRequest, request: Request):
    """
    API endpoint to generate/send a message to a specific chat via the bot.
    Requires 'X-API-Key' in headers for authentication.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    # Validate API Key
    key_doc = await db.api_keys.find_one({"api_key": api_key})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    # Check for expiration
    if datetime.utcnow() > key_doc["expires_at"]:
        raise HTTPException(status_code=403, detail="API Key expired")

    chat_id = req.chat_id
    prompt = req.prompt
    start_message_id = None
    
    try:
        # Send a starting message to indicate processing
        start_msg = await pyro_app.send_message(chat_id, "**✨ Processing your request...**")
        start_message_id = start_msg.id
        
        # Send the actual prompt (simulating the G4F generation/result)
        await pyro_app.send_message(chat_id, prompt)
        
        # Edit the starting message to show success
        await pyro_app.edit_message_text(
            chat_id,
            start_message_id,
            "✅ **Message sent successfully.**"
        )
        
        return {"status": "success", "sent": prompt, "to": chat_id, "key_user": key_doc["username"]}
        
    except Exception as e:
        # Edit the starting message to show failure if possible
        if start_message_id:
            await pyro_app.edit_message_text(chat_id, start_message_id, f"❌ Failed: {e}")
        
        # Re-raise as an HTTP exception
        raise HTTPException(status_code=500, detail=str(e))
