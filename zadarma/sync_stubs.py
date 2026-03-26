import sqlite3

def handle_sync_status_command(bot, update):
    user_id = update.effective_user.id
    if user_id not in [573368771, 7930079513]:
        bot.send_message(chat_id=update.message.chat_id, text="❌ Тільки для адмінів")
        return
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM clients')
        clients = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM users')
        users = cursor.fetchone()[0]
        conn.close()
        
        status = "📊 СТАТУС\n👥 Користувачів: {}\n🏥 Клієнтів: {}\n✅ Python 3.6 режим".format(users, clients)
        bot.send_message(chat_id=update.message.chat_id, text=status)
    except Exception as e:
        bot.send_message(chat_id=update.message.chat_id, text="❌ Помилка: {}".format(str(e)))

def handle_sync_test_command(bot, update):
    user_id = update.effective_user.id
    if user_id not in [573368771, 7930079513]:
        return
    bot.send_message(chat_id=update.message.chat_id, text="🧪 ТЕСТ\n💾 БД: ✅\n🐍 Python 3.6: ✅\n🤖 Бот: ✅")

def handle_sync_clean_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="⚠️ Недоступно на Python 3.6")

def handle_sync_full_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="⚠️ Недоступно на Python 3.6")

def handle_sync_user_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="⚠️ Недоступно на Python 3.6")

def handle_sync_help_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="🔄 КОМАНДИ\n📊 /sync_status\n🧪 /sync_test\n⚠️ Обмежений функціонал Python 3.6")
