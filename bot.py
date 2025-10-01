from pyrogram import Client, filters
from pyrogram.types import Message
import os
import httpx

# ===== Environment Variables =====
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
G4F_API_URL = os.environ.get("G4F_API_URL", "https://your-g4f-app.herokuapp.com")

# ===== Initialize Pyrogram Client =====
app = Client("g4f_key_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ===== Start Command =====
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "🤖 Welcome to G4F Key Generator Bot!\n\n"
        "Use /gen_key to generate a 30-day valid API key."
    )

# ===== Help Command =====
@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    await message.reply_text(
        "📌 Commands:\n"
        "/gen_key - Generate a 30-day valid API key"
    )

# ===== Generate API Key =====
@app.on_message(filters.command("gen_key") & filters.private)
async def gen_key_handler(client: Client, message: Message):
    try:
        async with httpx.AsyncClient(timeout=10) as session:
            res = await session.post(f"{G4F_API_URL}/gen_key")
            res.raise_for_status()
            data = res.json()

        key = data.get("key")
        expiry = data.get("expiry")

        if not key or not expiry:
            await message.reply_text("❌ Failed to retrieve key. Try again later.")
            return

        # ✅ Plain text reply
        await message.reply_text(f"✅ Your API key:\n{key}\nValid until: {expiry}")

    except Exception as e:
        print(f"Error generating key: {e}")
        await message.reply_text("❌ Failed to generate API key. Try again later.")

# ===== Run Bot =====
if __name__ == "__main__":
    print("🤖 G4F Key Generator Bot is starting...")
    app.run()
