from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
import os
import httpx
import json
import uuid

# ===== Environment Variables =====
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
G4F_API_URL = os.environ.get("G4F_API_URL", "https://your-g4f-app.herokuapp.com")

# ===== Admin User ID =====
ADMIN_ID = 7666870729  # Replace with your Telegram ID

# ===== Wallet File =====
WALLET_FILE = "wallet.json"

def load_wallet():
    try:
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_wallet(wallet):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet, f)

# ===== Initialize Pyrogram Client =====
app = Client(
    "g4f_key_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Unique bot ID for API key restriction
BOT_UNIQUE_ID = str(uuid.uuid4())

# ===== Start Command =====
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    wallet = load_wallet()
    user_id = str(message.from_user.id)

    if user_id not in wallet:
        wallet[user_id] = 100  # First time bonus
        save_wallet(wallet)

    buttons = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("➕ Add Points", callback_data="add_points")],
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ]
    await message.reply_text(
        f"🤖 <b>Welcome to Espro Key Generator Bot!</b>\n\n"
        f"💰 Your wallet: <b>{wallet[user_id]}</b> points\n"
        f"🔹 Generating an API key requires 300 points.\n\n"
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
        "✅ <code>/gen_key</code> → Generate a 30-day valid API key (300 points)\n"
        "✅ <code>/help</code> → Show this help menu\n"
        "✅ <code>/add_points &lt;user_id&gt; &lt;points&gt;</code> → Add points (Admin only)\n\n"
        "⚡ You can also use the buttons below for navigation.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

# ===== Gen Key Logic =====
async def gen_key_logic(user_id):
    wallet = load_wallet()
    points = wallet.get(user_id, 0)

    if points < 300:
        return False, points  # Not enough points

    # Deduct points
    wallet[user_id] -= 300
    save_wallet(wallet)
    return True, wallet[user_id]

# ===== Callback Handler =====
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = str(callback_query.from_user.id)

    if data == "help":
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await callback_query.message.edit_text(
            "📌 <b>Available Commands:</b>\n\n"
            "✅ <code>/gen_key</code> → Generate a 30-day valid API key (300 points)\n"
            "✅ <code>/help</code> → Show this help menu\n"
            "✅ <code>/add_points &lt;user_id&gt; &lt;points&gt;</code> → Add points (Admin only)\n\n"
            "⚡ Use the buttons below for navigation.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "back":
        buttons = [
            [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
            [InlineKeyboardButton("➕ Add Points", callback_data="add_points")],
            [InlineKeyboardButton("📖 Help", callback_data="help")]
        ]
        wallet = load_wallet()
        points = wallet.get(user_id, 0)
        await callback_query.message.edit_text(
            f"🤖 <b>Welcome back to Espro Key Generator Bot!</b>\n\n"
            f"💰 Your wallet: <b>{points}</b> points\n"
            "👇 Choose an option below:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "gen_key":
        success, points_left = await gen_key_logic(user_id)
        if not success:
            await callback_query.message.reply_text(
                f"❌ You need 300 points to generate an API key.\n"
                f"💰 Your current points: {points_left}",
                parse_mode=ParseMode.HTML
            )
            return

        # Generate API Key from backend
        try:
            async with httpx.AsyncClient(timeout=10) as session:
                res = await session.post(f"{G4F_API_URL}/gen_key", json={"bot_id": BOT_UNIQUE_ID})
                res.raise_for_status()
                data = res.json()

            if "error" in data:
                await callback_query.message.reply_text(
                    f"❌ {data['error']}",
                    parse_mode=ParseMode.HTML
                )
                return

            key = data.get("key")
            expiry = data.get("expiry")

            if not key or not expiry:
                await callback_query.message.reply_text(
                    "❌ Failed to retrieve API key. Try again later.",
                    parse_mode=ParseMode.HTML
                )
                return

            await callback_query.message.reply_text(
                f"✅ <b>Your API key:</b>\n<code>{key}</code>\n\n📅 <b>Valid until:</b> {expiry}\n"
                f"💰 Remaining points: <b>{points_left}</b>",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            print(f"Error generating key: {e}")
            await callback_query.message.reply_text(
                "❌ Failed to generate API key. Try again later.",
                parse_mode=ParseMode.HTML
            )

    elif data == "add_points":
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.message.reply_text(
                "❌ You are not authorized to add points.\n"
                "⚡ Please contact the admin to add points."
            )
        else:
            await callback_query.message.reply_text(
                "⚡ Admin: Use the command below to add points:\n"
                "/add_points <user_id> <points>"
            )

# ===== /gen_key command =====
@app.on_message(filters.command("gen_key") & filters.private)
async def gen_key_command(client: Client, message: Message):
    user_id = str(message.from_user.id)
    success, points_left = await gen_key_logic(user_id)
    if not success:
        await message.reply_text(
            f"❌ You need 300 points to generate an API key.\n"
            f"💰 Your current points: {points_left}",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        async with httpx.AsyncClient(timeout=10) as session:
            res = await session.post(f"{G4F_API_URL}/gen_key", json={"bot_id": BOT_UNIQUE_ID})
            res.raise_for_status()
            data = res.json()

        if "error" in data:
            await message.reply_text(
                f"❌ {data['error']}",
                parse_mode=ParseMode.HTML
            )
            return

        key = data.get("key")
        expiry = data.get("expiry")

        if not key or not expiry:
            await message.reply_text("❌ Failed to retrieve key. Try again later.", parse_mode=ParseMode.HTML)
            return

        await message.reply_text(
            f"✅ <b>Your API key:</b>\n<code>{key}</code>\n\n📅 <b>Valid until:</b> {expiry}\n"
            f"💰 Remaining points: <b>{points_left}</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        print(f"Error generating key: {e}")
        await message.reply_text("❌ Failed to generate API key. Try again later.", parse_mode=ParseMode.HTML)

# ===== Admin Command: Add Points =====
@app.on_message(filters.command("add_points") & filters.private)
async def add_points(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text(
            "❌ You are not authorized to add points.\n"
            "⚡ Please contact the admin to add points."
        )
        return

    try:
        parts = message.text.split()
        user_id = parts[1]
        points = int(parts[2])

        wallet = load_wallet()
        wallet[user_id] = wallet.get(user_id, 0) + points
        save_wallet(wallet)

        await message.reply_text(f"✅ Added {points} points to user {user_id}.\n💰 Total points: {wallet[user_id]}", parse_mode=ParseMode.HTML)

    except Exception as e:
