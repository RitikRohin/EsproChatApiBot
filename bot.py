from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
import os
import httpx

# ===== Environment Variables =====
API_ID = int(os.environ.get("API_ID", "123456"))  # Replace with your API_ID
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
G4F_API_URL = os.environ.get("G4F_API_URL", "https://your-g4f-app.herokuapp.com")

# ===== Initialize Pyrogram Client =====
app = Client(
    "g4f_key_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ===== Start Command =====
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    buttons = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ]
    await message.reply_text(
        "🤖 <b>Welcome to Espro Key Generator Bot!</b>\n\n"
        "🔹 Easily generate a 30-day valid API key.\n"
        "🔹 Use it for your Espro-based applications.\n\n"
        "👇 Choose an option below:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ===== Help Command =====
@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await message.reply_text(
        "📌 <b>Available Commands:</b>\n\n"
        "✅ <code>/gen_key</code> → Generate a 30-day valid API key\n"
        "✅ <code>/help</code> → Show this help menu\n\n"
        "⚡ You can also use the buttons below for easy navigation.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ===== Gen Key Command =====
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

        await message.reply_text(
            f"✅ <b>Your API key:</b>\n<code>{key}</code>\n\n📅 <b>Valid until:</b> {expiry}",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        print(f"Error generating key: {e}")
        await message.reply_text("❌ Failed to generate API key. Try again later.")


# ===== Callback Handler for Buttons =====
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data

    if data == "help":
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await callback_query.message.edit_text(
            "📌 <b>Available Commands:</b>\n\n"
            "✅ <code>/gen_key</code> → Generate a 30-day valid API key\n"
            "✅ <code>/help</code> → Show this help menu\n\n"
            "⚡ You can also use the buttons below for easy navigation.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "back":
        buttons = [
            [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
            [InlineKeyboardButton("📖 Help", callback_data="help")]
        ]
        await callback_query.message.edit_text(
            "🤖 <b>Welcome back to Espro Key Generator Bot!</b>\n\n"
            "👇 Choose an option below:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "gen_key":
        try:
            async with httpx.AsyncClient(timeout=10) as session:
                res = await session.post(f"{G4F_API_URL}/gen_key")
                res.raise_for_status()
                data = res.json()

            key = data.get("key")
            expiry = data.get("expiry")

            if not key or not expiry:
                await callback_query.message.reply_text("❌ Failed to retrieve key. Try again later.")
                return

            await callback_query.message.reply_text(
                f"✅ <b>Your API key:</b>\n<code>{key}</code>\n\n📅 <b>Valid until:</b> {expiry}",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            print(f"Error generating key: {e}")
            await callback_query.message.reply_text("❌ Failed to generate API key. Try again later.")


# ===== Run Bot =====
if __name__ == "__main__":
    print("🤖 Espro Key Generator Bot is starting...")
    app.run()
