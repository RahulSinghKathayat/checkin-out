import os
import threading
import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip("\"'")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip("\"'") 
checkout_tasks = {}
is_checked_in = False
telegram_app = None

DIGITS = {
    '0': ["┌─┐", "│ │", "└─┘"],
    '1': [" ┐ ", " │ ", " ┴ "],
    '2': ["┌─┐", "┌─┘", "└──"],
    '3': ["┌─┐", " ─┤", "└─┘"],
    '4': ["│ │", "└─┤", "  ┴"],
    '5': ["┌─┐", "└─┐", "└─┘"],
    '6': ["┌─┐", "├─┐", "└─┘"],
    '7': ["──┐", "  │", "  ┴"],
    '8': ["┌─┐", "├─┤", "└─┘"],
    '9': ["┌─┐", "└─┤", "──┘"],
    ':': ["   ", " ┬ ", " ┴ "],
    '-': ["   ", "───", "   "],
    ' ': ["   ", "   ", "   "]
}

def render_ascii_str(text):
    lines = ["", "", ""]
    for char in text:
        glyph = DIGITS.get(char, ["   ", "   ", "   "])
        for i in range(3):
            lines[i] += glyph[i] + " "
    return "```\n" + "\n".join(lines) + "\n```"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self):
        global is_checked_in
        if self.path == "/trigger-checkin":
            if not is_checked_in:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": CHAT_ID,
                    "text": "📍 Detected Office Wi-Fi. Do you want to check in?",
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Yes", "callback_data": "checkin_yes"},
                                {"text": "❌ No", "callback_data": "checkin_no"}
                            ],
                            [
                                {"text": "Cancel", "callback_data": "cancel_action"}
                            ]
                        ]
                    }
                }
                requests.post(url, json=payload)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Prompt sent")
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Already checked in, ignored.")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

async def checkout_loop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    await asyncio.sleep(33300) 
    while True:
        keyboard = [
            [
                InlineKeyboardButton("✅ Check Out", callback_data="checkout_yes"),
                InlineKeyboardButton("❌ Ignore", callback_data="checkout_no"),
            ],
            [
                InlineKeyboardButton("🚫 Cancel (Week Off / Manual)", callback_data="cancel_action"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Shift complete! It has been 9 hours 15 minutes. Do you want to check out?",
                reply_markup=reply_markup
            )
        except Exception:
            pass
        await asyncio.sleep(600)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="checkin_yes"),
            InlineKeyboardButton("No", callback_data="checkin_no"),
        ],
        [
            InlineKeyboardButton("🚫 Cancel (Week Off / Manual)", callback_data="cancel_action"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(
            "👋 Good morning! Would you like to check in for today?",
            reply_markup=reply_markup,
        )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_checked_in
    query = update.callback_query
    if not query:
        return

    await query.answer()
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id

    if query.data == "cancel_action":
        is_checked_in = False
        if chat_id in checkout_tasks:
            checkout_tasks[chat_id].cancel()
            del checkout_tasks[chat_id]
        await query.edit_message_text("🚫 Cancelled. Logged as week off or manual entry. Have a great day!")

    elif query.data == "checkin_yes":
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
        
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        date_ascii = render_ascii_str(now.strftime("%Y-%m-%d"))
        time_ascii = render_ascii_str(now.strftime("%H:%M:%S"))
        
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
                is_checked_in = True
                msg_text = (
                    "✅ *Successfully Checked In*\n\n"
                    "*Date:*\n"
                    f"{date_ascii}\n"
                    "*Time:*\n"
                    f"{time_ascii}\n"
                    "I will remind you to check out in 9 hours 15 minutes."
                )
                await query.edit_message_text(msg_text, parse_mode="Markdown")
                if chat_id in checkout_tasks:
                    checkout_tasks[chat_id].cancel()
                checkout_tasks[chat_id] = context.application.create_task(checkout_loop(context, chat_id))
            else:
                await query.edit_message_text(f"Check-in failed. Server response code: {response.status_code}")
        except Exception as e:
            await query.edit_message_text(f"Error connecting to HRMS: {str(e)}")
            
    elif query.data == "checkin_no":
        await query.edit_message_text("Ignored. Have a great day!")

    elif query.data == "checkout_yes":
        await query.edit_message_text("⏳ Processing office check-out via Novostack HRMS...")
        
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
        
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        date_ascii = render_ascii_str(now.strftime("%Y-%m-%d"))
        time_ascii = render_ascii_str(now.strftime("%H:%M:%S"))
        
        payload = {
            "doc": {
                "doctype": "Employee Checkin",
                "employee": "NS-EMP-00062",
                "log_type": "OUT",
                "time": current_time,
                "latitude": 28.854429032022278,
                "longitude": 78.76918758075675
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                is_checked_in = False 
                msg_text = (
                    "✅ *Successfully Checked Out*\n\n"
                    "*Date:*\n"
                    f"{date_ascii}\n"
                    "*Time:*\n"
                    f"{time_ascii}\n"
                    "See you tomorrow!"
                )
                await query.edit_message_text(msg_text, parse_mode="Markdown")
                if chat_id in checkout_tasks:
                    checkout_tasks[chat_id].cancel()
                    del checkout_tasks[chat_id]
            else:
                await query.edit_message_text(f"Check-out failed. Server response code: {response.status_code}")
        except Exception as e:
            await query.edit_message_text(f"Error connecting to HRMS: {str(e)}")

    elif query.data == "checkout_no":
        is_checked_in = False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await query.edit_message_text(f"Checkout alert ignored at {now_str}. I will remind you again in 10 minutes.")

def main():
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (add it to .env)")

    if not CHAT_ID:
        raise SystemExit("TELEGRAM_CHAT_ID is not set (add it to Render env vars)")

    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "checkin"], start))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()