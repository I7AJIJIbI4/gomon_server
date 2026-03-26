# 🔄 Інструкція для оновлення існуючого проєкту

## Швидке оновлення на сервері

### 1. Push змін на GitHub (локально):
```bash
cd zadarma/
git add .
git commit -m "🧹 Cleaned project structure"
git push origin main
```

### 2. Оновлення на сервері:
```bash
cd /home/gomoncli/zadarma
chmod +x update.sh
./update.sh
```

## Що робить скрипт update.sh:

1. ✅ **Backup важливих файлів** (config.py, users.db, .env, логи)
2. 🛑 **Зупиняє бота** безпечно
3. 🔄 **Оновлює код** з GitHub
4. 📁 **Відновлює конфігурацію** з backup
5. ✅ **Перевіряє валідність** config.py
6. 📦 **Оновлює залежності** Python
7. 🔧 **Налаштовує права** доступу
8. 🌐 **Перевіряє API** (швидко)
9. 🚀 **Запускає бота** знову
10. 🗑️ **Очищає старі backup'и**

## Ручне оновлення (якщо щось пішло не так):

```bash
cd /home/gomoncli/zadarma

# Зупинити бота
pkill -f "python3.*bot.py"

# Зберегти важливе
cp config.py config.py.backup
cp users.db users.db.backup

# Оновити код
git fetch origin
git reset --hard origin/main

# Відновити конфігурацію
cp config.py.backup config.py
cp users.db.backup users.db

# Оновити залежності
pip3 install -r requirements.txt --user --upgrade

# Запустити
chmod +x run_script.sh
./run_script.sh
```

## Перевірка після оновлення:

```bash
# Статус бота
ps aux | grep bot.py

# Логи
tail -f bot.log

# Webhook логи
tail -f webhook_processor.log

# API перевірка
./api_check.sh
```

## У разі проблем:

1. **Бот не запускається** - перевірте `bot.log`
2. **Конфігурація некоректна** - відредагуйте `config.py`
3. **API не працює** - запустіть `./api_check.sh`
4. **Webhook не працює** - перевірте `webhook_processor.log`

## Rollback (відкат):

Якщо щось пішло не так, backup зберігається в:
```bash
/home/gomoncli/backup/zadarma_update_YYYYMMDD_HHMMSS/
```

Відновлення:
```bash
cp /home/gomoncli/backup/zadarma_update_*/config.py /home/gomoncli/zadarma/
cp /home/gomoncli/backup/zadarma_update_*/users.db /home/gomoncli/zadarma/
cd /home/gomoncli/zadarma
./run_script.sh
```
