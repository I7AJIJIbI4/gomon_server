# Інструкції з інтеграції webhook системи

## 🎯 Мета
Замінити поллінг API (кожні 3 секунди) на webhook систему для уникнення rate limiting.

## 📋 Кроки інтеграції

### 1. Завантаження нових файлів на сервер

```bash
# Підключитися до сервера
ssh gomoncli@your-server.com

# Перейти в папку проекту
cd /home/gomoncli/zadarma

# Створити резервні копії
cp zadarma_api.py zadarma_api_backup.py
cp zadarma_call.py zadarma_call_backup.py
cp bot.py bot_backup.py

# Завантажити нові файли з локального репозиторію (після git push)
git pull origin main
```

### 2. Копіювання webhook файлів в public_html

```bash
# Скопіювати webhook файли
cp /home/gomoncli/zadarma/webhooks/telegram_webhook.php /home/gomoncli/public_html/
chmod 644 /home/gomoncli/public_html/telegram_webhook.php

# Зробити Python файли виконуваними
chmod +x /home/gomoncli/zadarma/process_webhook.py
```

### 3. Оновлення bot.py для використання нових модулів

Редагувати `/home/gomoncli/zadarma/bot.py`:

```python
# Замінити рядок:
# from zadarma_call import handle_door_command, handle_gate_command, handle_admin_stats_command

# На:
from zadarma_call_webhook import handle_door_command, handle_gate_command, handle_admin_stats_command
```

### 4. Налаштування Zadarma webhook

1. Зайти в панель керування Zadarma
2. Перейти в розділ "Webhooks" 
3. Додати новий webhook:
   - URL: `https://your-domain.com/telegram_webhook.php`
   - Події: `NOTIFY_START`, `NOTIFY_END`
   - Метод: POST

### 5. Тестування

```bash
# Перезапустити бота
pkill -f bot.py
cd /home/gomoncli/zadarma && python3 bot.py &

# Перевірити логи
tail -f /home/gomoncli/zadarma/bot.log

# Протестувати команди
# У Telegram боті: /hvirtka або /vorota

# Перевірити webhook логи
tail -f /home/gomoncli/zadarma/telegram_webhook.log
tail -f /home/gomoncli/zadarma/webhook_processor.log
```

### 6. Перевірка роботи

Після успішної інтеграції:

1. ✅ **Команди /hvirtka та /vorota** мають працювати
2. ✅ **Результат** має приходити протягом 30 секунд через webhook
3. ✅ **Немає помилок** rate limiting в логах
4. ✅ **База даних** `call_tracking.db` створюється автоматично

### 7. Моніторинг

```bash
# Перевірити відсутність rate limiting помилок
grep -i "rate limit" /home/gomoncli/zadarma/bot.log

# Перевірити роботу webhook
grep -i "success\|failed" /home/gomoncli/zadarma/webhook_processor.log

# Перевірити базу даних
ls -la /home/gomoncli/zadarma/call_tracking.db
```

## 🔄 Відкат у разі проблем

```bash
# Повернути старі файли
cp zadarma_api_backup.py zadarma_api.py
cp zadarma_call_backup.py zadarma_call.py
cp bot_backup.py bot.py

# Перезапустити бота
pkill -f bot.py
cd /home/gomoncli/zadarma && python3 bot.py &
```

## 📊 Переваги нової системи

1. **Відсутність rate limiting** - немає постійних API запитів
2. **Швидший відгук** - результат через webhook за секунди
3. **Надійність** - менше точок відмови
4. **Логування** - повна історія операцій в базі даних
5. **Масштабованість** - підтримка багатьох користувачів одночасно

## ⚠️ Важливі примітки

- Webhook URL має бути доступний з інтернету
- Python скрипти мають права на виконання
- База даних створюється автоматично при першому запуску
- Логи зберігаються в `/home/gomoncli/zadarma/`
- Резервні копії важливо зберегти для відкату

## 🔧 Налагодження проблем

### Якщо webhook не працює:
```bash
# Перевірити доступність URL
curl -X POST https://your-domain.com/telegram_webhook.php

# Перевірити права файлів
ls -la /home/gomoncli/public_html/telegram_webhook.php
ls -la /home/gomoncli/zadarma/process_webhook.py
```

### Якщо Python скрипт не запускається:
```bash
# Перевірити Python та залежності
cd /home/gomoncli/zadarma
python3 process_webhook.py '{"test": "data"}'
```

### Якщо база даних не створюється:
```bash
# Перевірити права папки
ls -la /home/gomoncli/zadarma/
touch /home/gomoncli/zadarma/test.db && rm /home/gomoncli/zadarma/test.db
```
