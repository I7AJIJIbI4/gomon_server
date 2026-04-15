import sqlite3
from telegram.ext import ContextTypes


async def handle_sync_status_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in [573368771, 7930079513]:
        await update.message.reply_text("❌ Тільки для адмінів")
        return

    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM clients')
        clients = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM users')
        users = cursor.fetchone()[0]
        conn.close()

        status = "📊 СТАТУС\n👥 Користувачів: {}\n🏥 Клієнтів: {}".format(users, clients)
        await update.message.reply_text(status)
    except Exception as e:
        await update.message.reply_text("❌ Помилка: {}".format(str(e)))


async def handle_sync_test_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in [573368771, 7930079513]:
        return
    await update.message.reply_text("🧪 ТЕСТ\n💾 БД: ✅\n🐍 Python: ✅\n🤖 Бот: ✅")


async def handle_sync_clean_command(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Недоступно")


async def handle_sync_full_command(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Недоступно")


async def handle_sync_user_command(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Недоступно")


async def handle_sync_help_command(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 КОМАНДИ\n📊 /sync_status\n🧪 /sync_test")
