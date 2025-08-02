import aiosqlite
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import logging
from dateutil.relativedelta import relativedelta
import pandas as pd
import nest_asyncio
import io

nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
TOKEN = '8064044877:AAGdHp4ICm5Sk4XJbg5lkWcpaCRCNzw96X4'  # ✅ Change to your token
user_state = {}

# Database setup
async def init_db():
    async with aiosqlite.connect("expenses.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                category TEXT,
                date TEXT
            )
        """)
        await db.commit()

async def add_expense(user_id, amount, category):
    async with aiosqlite.connect("expenses.db") as db:
        await db.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, category, datetime.now().isoformat())
        )
        await db.commit()

async def get_expense_summary(user_id, start_date=None, end_date=None):
    query = "SELECT category, SUM(amount) FROM expenses WHERE user_id = ?"
    params = [user_id]
    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date.isoformat(), end_date.isoformat()])
    query += " GROUP BY category"
    async with aiosqlite.connect("expenses.db") as db:
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_user_expenses(user_id):
    async with aiosqlite.connect("expenses.db") as db:
        async with db.execute("SELECT id, amount, category, date FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,)) as cursor:
            return await cursor.fetchall()

async def delete_expense(expense_id):
    async with aiosqlite.connect("expenses.db") as db:
        await db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        await db.commit()

def get_date_filter(filter_type):
    now = datetime.now()
    if filter_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif filter_type == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif filter_type == "this_week":
        start = now - timedelta(days=now.weekday())
        end = now
    elif filter_type == "last_week":
        start = now - timedelta(days=now.weekday() + 7)
        end = start + timedelta(days=7)
    elif filter_type == "this_month":
        start = now.replace(day=1)
        end = now
    elif filter_type == "last_month":
        first_day_this_month = now.replace(day=1)
        start = first_day_this_month - relativedelta(months=1)
        end = first_day_this_month
    else:
        return None, None
    return start, end

# Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("សូមបញ្ចូលចំនួនលុយដែលបានចំណាយ​​ ❤️😍  (NOTE : លុយគិតជាលុយរៀល [៛])😘")
    user_state[update.effective_user.id] = {"step": "awaiting_amount"}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
🤖 <b>ជំនួយ:</b>
/start - ចាប់ផ្ដើមចំណាយថ្មី
/report - បង្ហាញរបាយការណ៍
/download - ទាញយកចំណាយជា Excel
/edit - លុបចំណាយចាស់ៗ
/help - ជំនួយ

ប្រើប៊ូតុង Inline ដើម្បីជ្រើសប្រភេទ ឬរបាយការណ៍។
""", parse_mode="HTML")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        return await update.message.reply_text("សូមវាយ /start ជាមុនសិន")

    state = user_state[user_id]

    if state["step"] == "awaiting_amount":
        try:
            amount = float(text)
            state["amount"] = amount
            state["step"] = "awaiting_category"
            keyboard = [
                [InlineKeyboardButton("អាហារ 🍚", callback_data='Food')],
                [InlineKeyboardButton("ការសិក្សា 📚✏️", callback_data='Study')],
                [InlineKeyboardButton("លេងកីឡា ⚽🎾", callback_data='Sport')],
                [InlineKeyboardButton("ធ្វើដំណើរ 🚗🚶🏍️", callback_data='Transport')],
                [InlineKeyboardButton("ផ្សេងៗ ✏️", callback_data='Other')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("ជ្រើសប្រភេទចំណាយ:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("សូមបញ្ចូលចំនួនជាលេខ! 😒")

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id in user_state and user_state[user_id]["step"] == "awaiting_category":
        amount = user_state[user_id]["amount"]
        category = query.data
        await add_expense(user_id, amount, category)
        await query.edit_message_text(f"✅✏️ បានរក្សាទុកចំណាយ៖ {amount}៛ ប្រភេទ៖ {category}")
        user_state.pop(user_id)

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("ថ្ងៃនេះ", callback_data='today')],
        [InlineKeyboardButton("ម្សិលមិញ", callback_data='yesterday')],
        [InlineKeyboardButton("សប្តាហ៍នេះ", callback_data='this_week')],
        [InlineKeyboardButton("សប្តាហ៍មុន", callback_data='last_week')],
        [InlineKeyboardButton("ខែនេះ", callback_data='this_month')],
        [InlineKeyboardButton("ខែមុន", callback_data='last_month')],
    ]
    await update.message.reply_text("ជ្រើសរបាយការណ៍:", reply_markup=InlineKeyboardMarkup(keyboard))

async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    filter_type = query.data
    start, end = get_date_filter(filter_type)
    rows = await get_expense_summary(user_id, start, end)

    if rows:
        response = f"📊 ចំណាយ {filter_type.replace('_', ' ')}:\n"
        for category, total in rows:
            response += f"• {category}: {total:.0f}៛\n"
    else:
        response = "🙁 គ្មានចំណាយ!"

    await query.edit_message_text(response)

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await get_user_expenses(user_id)
    if not rows:
        return await update.message.reply_text("គ្មានទិន្នន័យ!")

    df = pd.DataFrame(rows, columns=["ID", "ចំនួន", "ប្រភេទ", "ថ្ងៃ"])
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    await update.message.reply_document(document=InputFile(output, filename="expenses.xlsx"))

async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await get_user_expenses(user_id)
    if not rows:
        return await update.message.reply_text("គ្មានទិន្នន័យ!")

    keyboard = []
    for row in rows[:5]:  # Limit to last 5 entries
        keyboard.append([InlineKeyboardButton(f"លុប {row[1]}៛ - {row[2]} - {row[3][:10]}", callback_data=f"del_{row[0]}")])

    await update.message.reply_text("ជ្រើសចំណាយដើម្បីលុប:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("del_"):
        expense_id = int(query.data.split("_")[1])
        await delete_expense(expense_id)
        await query.edit_message_text("✅ បានលុបចំណាយ។")

# Run bot
if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("edit", edit))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_category, pattern="^(Food|Study|Sport|Transport|Other)$"))
    app.add_handler(CallbackQueryHandler(report_callback, pattern="^(today|yesterday|this_week|last_week|this_month|last_month)$"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^del_"))
    print("🤖 Bot is running...")
    app.run_polling()
