from pyrogram import Client, filters
from pyrogram.types import Message
import requests, os

API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
G4F_API_URL = os.environ.get("G4F_API_URL", "https://esproapi.herokuapp.com")

app = Client("g4f_key_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text("🤖 Welcome to G4F Key Generator Bot!\nUse /gen_key to generate API key.")

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    await message.reply_text("/gen_key - Generate a 30-day valid API key")

@app.on_message(filters.command("gen_key") & filters.private)
async def gen_key_handler(client: Client, message: Message):
    try:
        res = requests.post(f"{G4F_API_URL}/gen_key")
        res.raise_for_status()
        data = res.json()
        key = data.get("key")
        expiry = data.get("expiry")
        await message.reply_text(f"✅ Your API key:\n`{key}`\nValid until: {expiry}", parse_mode="markdown")
    except Exception as e:
        await message.reply_text(f"❌ Error generating key: {e}")

if __name__ == "__main__":
    print("Telegram Key Generator Bot starting...")
    app.run()
