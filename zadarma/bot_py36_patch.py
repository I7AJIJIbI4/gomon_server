#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_py36_patch.py - Патч для bot.py під Python 3.6
"""

# Створюємо патч для bot.py
patch_content = '''
# Заміна імпорту sync_management на sync_management_py36
# Додайте після рядка з іншими імпортами:

try:
    # Спочатку намагаємось імпортувати повну версію
    from sync_management import (
        handle_sync_status_command, handle_sync_clean_command, handle_sync_full_command,
        handle_sync_test_command, handle_sync_user_command, handle_sync_help_command
    )
    print("✅ Завантажено повну версію sync_management")
except ImportError:
    # Якщо не вдається, використовуємо Python 3.6 сумісну версію
    try:
        from sync_management_py36 import (
            handle_sync_status_command, handle_sync_test_command, handle_sync_help_command
        )
        print("⚠️ Завантажено базову версію sync_management для Python 3.6")
        
        # Заглушки для відсутніх функцій
        def handle_sync_clean_command(bot, update):
            user_id = update.effective_user.id
            bot.send_message(
                chat_id=update.message.chat_id,
                text="⚠️ Функція очищення дублікатів тимчасово недоступна"
            )
        
        def handle_sync_full_command(bot, update):
            bot.send_message(
                chat_id=update.message.chat_id,
                text="⚠️ Повна синхронізація тимчасово недоступна"
            )
            
        def handle_sync_user_command(bot, update):
            bot.send_message(
                chat_id=update.message.chat_id,
                text="⚠️ Синхронізація користувача тимчасово недоступна"
            )
            
    except ImportError as e:
        print("❌ Не вдалось завантажити жодну версію sync_management: {}".format(e))
        
        # Мінімальні заглушки
        def handle_sync_status_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
        
        def handle_sync_clean_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
            
        def handle_sync_full_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
            
        def handle_sync_test_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
            
        def handle_sync_user_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
            
        def handle_sync_help_command(bot, update):
            bot.send_message(chat_id=update.message.chat_id, text="❌ Модуль синхронізації недоступний")
'''

print("📝 Створюємо патч для bot.py...")
print("Вам потрібно замінити в bot.py рядки імпорту sync_management на наведений вище код")
print("")
print("🔧 АБО запустити цей патч автоматично:")

# Створюємо скрипт автоматичного патчингу
auto_patch = '''#!/bin/bash
# auto_patch_bot.sh - Автоматичний патч bot.py

echo "🔧 Автоматичне патчингу bot.py..."

# Створюємо backup
cp bot.py bot.py.backup.$(date +%Y%m%d_%H%M%S)

# Замінюємо проблемний імпорт
sed -i 's/from sync_management import/#from sync_management import/' bot.py

# Додаємо новий імпорт після рядка з config
sed -i '/from config import/a\\
\\
# Python 3.6 compatible sync_management import\\
try:\\
    from sync_management_py36 import handle_sync_status_command, handle_sync_test_command, handle_sync_help_command\\
    print("✅ Завантажено sync_management для Python 3.6")\\
    \\
    def handle_sync_clean_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="⚠️ Очищення дублікатів тимчасово недоступне")\\
    \\
    def handle_sync_full_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="⚠️ Повна синхронізація тимчасово недоступна")\\
    \\
    def handle_sync_user_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="⚠️ Синхронізація користувача тимчасово недоступна")\\
except ImportError:\\
    print("❌ sync_management недоступний")\\
    def handle_sync_status_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")\\
    def handle_sync_clean_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")\\
    def handle_sync_full_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")\\
    def handle_sync_test_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")\\
    def handle_sync_user_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")\\
    def handle_sync_help_command(bot, update):\\
        bot.send_message(chat_id=update.message.chat_id, text="❌ Синхронізація недоступна")
' bot.py

echo "✅ bot.py пропатчено для Python 3.6"
echo "📋 Backup: bot.py.backup.*"
'''

with open('/Users/ipavlovsky/Library/CloudStorage/GoogleDrive-samydoma@gmail.com/My Drive/zadarma/auto_patch_bot.sh', 'w') as f:
    f.write(auto_patch)

print("✅ Створено auto_patch_bot.sh")
