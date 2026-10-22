import os
from datetime import datetime
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 1. Action to send prompt with check-in buttons (/start or /checkin)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="checkin_yes"),
            InlineKeyboardButton("❌ No", callback_data="checkin_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(
            "👋 Good morning! Would you like to check in for today?",
            reply_markup=reply_markup,
        )

# 2. Action executed when you tap a button
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == "checkin_yes":
        await query.edit_message_text("⏳ Processing office check-in via Novostack HRMS...")
        
        url = "https://hrms.novostack.com/api/method/frappe.client.insert"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "cookie": "user_lang=en; sid=136f223e0a3592dae9515074cd9e9c1ae192314c3394b4c26694d14a; system_user=yes; full_name=Rahul%20Kathayat; user_id=rahul.kathayat%40novostack.com",
            "origin": "https://hrms.novostack.com",
            "referer": "https://hrms.novostack.com/hrms/home",
            "x-frappe-csrf-token": "98d86c97874f0dc6fdebdd4773ec83615b6048acc0b5f2c9d1dad102",
            "x-frappe-site-name": "hrms.novostack.com",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        # Dynamically generate the current timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        payload = {
            "doc": {
                "doctype": "Employee Checkin",
                "employee": "NS-EMP-00062",
                "log_type": "IN",
                "time": current_time,
                "latitude": 28.854429032022278,
                "longitude": 78.76918758075675
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                await query.edit_message_text(f"✅ Successfully checked in at {current_time}!")
            else:
                await query.edit_message_text(f"❌ Check-in failed. Server response code: {response.status_code}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error connecting to HRMS: {str(e)}")
            
    elif query.data == "checkin_no":
        await query.edit_message_text("👍 Ignored. Have a great day!")

def main():
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (add it to .env)")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler(["start", "checkin"], start))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()