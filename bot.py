from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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
    buttons = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ]
    await message.reply_text(
        "🤖 **Welcome to Espro Key Generator Bot!**\n\n"
        "🔹 Easily generate a 30-day valid API key.\n"
        "🔹 Use it for your Espro-based applications.\n\n"
        "👇 Choose an option below:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ===== Help Command =====
@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    buttons = [
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await message.reply_text(
        "📌 **Available Commands:**\n\n"
        "✅ `/gen_key` → Generate a 30-day valid API key\n"
        "✅ `/help` → Show this help menu\n\n"
        "⚡ You can also use the buttons below for easy navigation.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ===== Callback Handler for Buttons =====
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data

    if data == "help":
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await callback_query.message.edit_text(
            "📌 **Available Commands:**\n\n"
            "✅ `/gen_key` → Generate a 30-day valid API key\n"
            "✅ `/help` → Show this help menu\n\n"
            "⚡ You can also use the buttons below for easy navigation.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "back":
        buttons = [
            [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
            [InlineKeyboardButton("📖 Help", callback_data="help")]
        ]
        await callback_query.message.edit_text(
            "🤖 **Welcome back to Espro Key Generator Bot!**\n\n"
            "👇 Choose an option below:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "gen_key":
        try:
            async with httpx.AsyncClient(timeout=10) as session:
                res = await session.post(f"{G4F_API_URL}/gen_key")
                res.raise_for_status()
                data = await res.json()

            key = data.get("key")
            expiry = data.get("expiry")

            if not key or not expiry:
                await callback_query.message.reply_text("❌ Failed to retrieve key. Try again later.")
                return

            await callback_query.message.reply_text(
                f"✅ **Your API key:**\n`{key}`\n\n\n📅 **Valid until:** {expiry}",
                parse_mode=None
            )

        except Exception as e:
            print(f"Error generating key: {e}")
            await callback_query.message.reply_text("❌ Failed to generate API key. Try again later.")


# ===== Run Bot =====
if __name__ == "__main__":
    print("🤖 Espro Key Generator Bot is starting...")
    app.run()
