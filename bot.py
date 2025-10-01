from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
import os
import httpx
import json
import uuid

# ===== Payment Configuration (CHANGE THESE) =====
# 🛑 IMPORTANT: Replace this with the public URL of your QR code image.
# NOTE: ibb.co links often point to an HTML page, not the direct image URL. 
# Make sure this link ends in .jpg, .png, etc., or it will fail to send the photo.
QR_CODE_IMAGE_URL = "https://ibb.co/zTPBVQxq" 
# 🛑 IMPORTANT: Replace this with your actual UPI ID.
YOUR_UPI_ID = "ritikrohin@airtel"

# ===== Environment Variables (Set these in your hosting environment) =====
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
G4F_API_URL = os.environ.get("G4F_API_URL", "https://your-g4f-app.herokuapp.com")

# ===== Admin User ID (Set this to your Telegram ID) =====
ADMIN_ID = 7666870729  

# ===== Wallet File and User State =====
WALLET_FILE = "wallet.json"
# Dictionary to temporarily track users who are submitting a UTR
user_states = {} 

def load_wallet():
    """Loads the user wallet data from a JSON file."""
    try:
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_wallet(wallet):
    """Saves the user wallet data to a JSON file."""
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet, f)

# ===== Initialize Pyrogram Client =====
app = Client(
    "g4f_key_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

BOT_UNIQUE_ID = str(uuid.uuid4())

# ===== Core Logic & Commands =====

async def gen_key_logic(user_id):
    """Handles point deduction before attempting key generation."""
    wallet = load_wallet()
    points = wallet.get(user_id, 0)

    if points < 300:
        return False, points

    wallet[user_id] -= 300
    save_wallet(wallet)
    return True, wallet[user_id]

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handles the /start command."""
    wallet = load_wallet()
    user_id = str(message.from_user.id)

    if user_id not in wallet:
        wallet[user_id] = 100
        save_wallet(wallet)

    buttons = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("💰 Check Points", callback_data="check_points")],
        [InlineKeyboardButton("➕ Add Points", callback_data="show_payment_menu")],
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

@app.on_message(filters.command(["points", "balance"]) & filters.private)
async def check_points_command(client: Client, message: Message):
    """Handles /points or /balance command."""
    user_id = str(message.from_user.id)
    wallet = load_wallet()
    points = wallet.get(user_id, 0)
    
    buttons = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    await message.reply_text(
        f"💰 **Your Current Wallet Balance:**\n"
        f"**{points}** points",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    """Handles the /help command."""
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await message.reply_text(
        "📌 <b>Available Commands:</b>\n\n"
        "✅ <code>/gen_key</code> → Generate a 30-day valid API key (300 points)\n"
        "✅ <code>/points</code> or <code>/balance</code> → Check your current points\n"
        "✅ <code>/help</code> → Show this help menu\n"
        "✅ <code>/add_points &lt;user_id&gt; &lt;points&gt;</code> → Add points (Admin only)\n\n"
        "⚡ You can also use the buttons below for navigation.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("gen_key") & filters.private)
async def gen_key_command(client: Client, message: Message):
    """Handles the /gen_key command and calls the API."""
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
            await message.reply_text(f"❌ {data['error']}", parse_mode=ParseMode.HTML)
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

@app.on_message(filters.command("add_points") & filters.private)
async def add_points(client, message: Message):
    """Admin command to add points to a user's wallet."""
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("❌ You are not authorized to add points.")
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
        print(f"Error adding points: {e}")
        await message.reply_text(
            "❌ Invalid command usage.\n"
            "⚡ **Usage:** `/add_points <user_id> <points>`"
        )
        
# --- FIXED FILTER HERE (Called filters.command() to fix TypeError) ---
@app.on_message(filters.text & filters.private & ~filters.command())
async def utr_submission_handler(client, message: Message):
    """Handles text messages and checks if the user is submitting a UTR."""
    user_id = str(message.from_user.id)
    
    if user_id in user_states and user_states[user_id]['action'] == 'submit_utr':
        utr_id = message.text.strip()
        points_to_add = user_states[user_id]['points']

        # Simple check if the UTR looks like a number/code
        if not utr_id.isalnum() or len(utr_id) < 10:
            await message.reply_text(
                "❌ **Invalid UTR.** Kripya sirf sahi Transaction ID (number ya code) hi dalein."
            )
            return

        # Send UTR to Admin
        await client.send_message(
            ADMIN_ID,
            f"🔔 **NEW UTR RECEIVED**\n\n"
            f"👤 User: {message.from_user.mention} (<code>{user_id}</code>)\n"
            f"💰 Expected Points: **{points_to_add}**\n"
            f"🔑 **UTR/Reference:** <code>{utr_id}</code>\n\n"
            f"Admin, payment verify karein aur points add karne ke liye yeh command use karein: "
            f"<code>/add_points {user_id} {points_to_add}</code>",
            parse_mode=ParseMode.HTML
        )

        # Confirm to User
        await message.reply_text(
            "✅ **UTR Safaltapoorvak Submit ho gaya hai!**\n"
            f"Aapki Transaction ID (<code>{utr_id}</code>) Admin ko bhej di gayi hai.\n\n"
            "🙏 Kripya **5 se 10 minute** intezaar karein. Payment verify hote hi aapke wallet mein **points add ho jayenge**."
            , parse_mode=ParseMode.HTML
        )

        # Clear the user's state
        del user_states[user_id]


# ===== Callback Handler =====

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = str(callback_query.from_user.id)
    wallet = load_wallet()

    if data == "help":
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await callback_query.message.edit_text(
            "📌 <b>Available Commands:</b>\n\n"
            "✅ <code>/gen_key</code> → Generate a 30-day valid API key (300 points)\n"
            "✅ <code>/points</code> or <code>/balance</code> → Check your current points\n"
            "✅ <code>/help</code> → Show this help menu\n"
            "✅ <code>/add_points &lt;user_id&gt; &lt;points&gt;</code> → Add points (Admin only)\n\n"
            "⚡ Use the buttons below for navigation.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )

    elif data == "back":
        points = wallet.get(user_id, 0)
        buttons = [
            [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
            [InlineKeyboardButton("💰 Check Points", callback_data="check_points")],
            [InlineKeyboardButton("➕ Add Points", callback_data="show_payment_menu")],
            [InlineKeyboardButton("📖 Help", callback_data="help")]
        ]
        await callback_query.message.edit_text(
            f"🤖 <b>Welcome back to Espro Key Generator Bot!</b>\n\n"
            f"💰 Your wallet: <b>{points}</b> points\n"
            "👇 Choose an option below:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "check_points":
        points = wallet.get(user_id, 0)
        
        buttons = [
            [InlineKeyboardButton("🔑 Generate Key", callback_data="gen_key")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]

        await callback_query.message.edit_text(
            f"💰 **Your Current Wallet Balance:**\n"
            f"**{points}** points\n\n"
            f"🔹 API Key generation costs 300 points.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
    # --- Show Payment Menu ---
    elif data == "show_payment_menu":
        buttons = [
            [InlineKeyboardButton("💵 ₹100 = 100 Points", callback_data="pay_100_100")],
            [InlineKeyboardButton("💵 ₹200 = 250 Points", callback_data="pay_200_250")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]
        await callback_query.message.edit_text(
            "⚡ **Points Recharge Menu**\n\n"
            "Please select the points package you wish to purchase:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
    # --- Handle Payment Initiation (Manual) ---
    elif data.startswith("pay_"):
        try:
            # Format: pay_<amount>_<points> (e.g., pay_100_100)
            parts = data.split('_')
            amount = parts[1]
            points_to_add = parts[2]
            
            await callback_query.message.delete()
            
            await client.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=QR_CODE_IMAGE_URL,
                caption=f"✅ **Scan and Pay ₹{amount}**\n\n"
                        f"**UPI ID:** <code>{YOUR_UPI_ID}</code>\n"
                        f"**Amount:** ₹{amount}.00\n"
                        f"**Points You Will Get:** {points_to_add}\n\n"
                        "➡️ **Payment ho chuka hai?** Neeche di gayi button par click karke apni Transaction ID (UTR/Reference No.) submit karein.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Submit UTR ID Now", callback_data=f"submit_utr_{points_to_add}")], 
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back")]
                ]),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await callback_query.message.reply_text("❌ Error processing payment request. Try again later.")
            print(f"Error in pay_ handler: {e}")

    # --- UTR Submission Starter ---
    elif data.startswith("submit_utr_"):
        points_to_add = data.split('_')[2]
        
        # Admin is notified immediately upon submission request
        await client.send_message(
            ADMIN_ID, 
            f"⚠️ **New UTR Submission Request!**\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Expected Points: {points_to_add}\n"
            f"Admin, payment check karne ke baad points add karne ke liye ready rahein.",
            parse_mode=ParseMode.HTML
        )
        
        # Inform the user and set their state to expect the UTR
        await callback_query.message.reply_text(
            "🔑 **Ab apni Transaction ID (UTR/Reference No.) reply karein.**\n"
            "Sirf number ya UTR code dalein, koi aur text nahi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Cancel Submission", callback_data="back")]
            ])
        )
        
        global user_states
        user_states[user_id] = {"action": "submit_utr", "points": points_to_add}

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
                await callback_query.message.reply_text(f"❌ {data['error']}", parse_mode=ParseMode.HTML)
                return

            key = data.get("key")
            expiry = data.get("expiry")

            if not key or not expiry:
                await callback_query.message.reply_text("❌ Failed to retrieve API key. Try again later.", parse_mode=ParseMode.HTML)
                return

            await callback_query.message.reply_text(
                f"✅ <b>Your API key:</b>\n<code>{key}</code>\n\n📅 <b>Valid until:</b> {expiry}\n"
                f"💰 Remaining points: <b>{points_left}</b>",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            print(f"Error generating key: {e}")
            await callback_query.message.reply_text("❌ Failed to generate API key. Try again later.", parse_mode=ParseMode.HTML)


# ===================================
# ===== BOT STARTUP =====
# ===================================

if __name__ == "__main__":
    app.run()
