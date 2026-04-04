# Міграція домену: gomonclinic.com → drgomon.com

## Передумови
- [ ] Домен drgomon.com куплений
- [ ] DNS направлений на сервер (31.131.18.79)
- [ ] SSL сертифікат отриманий (Let's Encrypt через LiteSpeed)
- [ ] Новий домен відкривається в браузері (хоча б default page)

## Скрипт міграції

### Крок 1: Змінні (заповнити перед запуском)
```bash
OLD_DOMAIN="www.gomonclinic.com"
NEW_DOMAIN="www.drgomon.com"
# Якщо без www:
# NEW_DOMAIN="drgomon.com"
```

### Крок 2: Backend (на сервері)

```bash
cd /home/gomoncli/zadarma

# pwa_api.py — CORS
sed -i "s|gomonclinic.com|drgomon.com|g" pwa_api.py

# notifier.py — лінки в повідомленнях
sed -i "s|gomonclinic.com|drgomon.com|g" notifier.py

# bot.py — лінки
sed -i "s|gomonclinic.com|drgomon.com|g" bot.py

# sync_clients.py — якщо є посилання
sed -i "s|gomonclinic.com|drgomon.com|g" sync_clients.py 2>/dev/null
```

### Крок 3: Frontend (на сервері)

```bash
cd /home/gomoncli/public_html

# manifest.json
sed -i "s|gomonclinic.com|drgomon.com|g" app/manifest.json

# sw.js — bump cache + URLs
sed -i "s|gomonclinic.com|drgomon.com|g" app/sw.js

# index.html
sed -i "s|gomonclinic.com|drgomon.com|g" app/index.html

# gomon-chat.js
sed -i "s|gomonclinic.com|drgomon.com|g" app/gomon-chat.js

# gomon-widget.js
sed -i "s|gomonclinic.com|drgomon.com|g" gomon-widget.js

# go.html
sed -i "s|gomonclinic.com|drgomon.com|g" go.html

# privacy-policy.html
sed -i "s|gomonclinic.com|drgomon.com|g" privacy-policy.html

# merchant-feed.xml
sed -i "s|gomonclinic.com|drgomon.com|g" merchant-feed.xml

# Site PHP
sed -i "s|gomonclinic.com|drgomon.com|g" sitepro/a188dd94d37a0374c81c636d09cd1f05.php

# promos.php
sed -i "s|gomonclinic.com|drgomon.com|g" promos.php

# PHP CORS files
sed -i "s|gomonclinic.com|drgomon.com|g" sitepro/prices.php
sed -i "s|gomonclinic.com|drgomon.com|g" sitepro/modal_prices.php
```

### Крок 4: System prompt (AI асистент)

```bash
sed -i "s|gomonclinic.com|drgomon.com|g" /home/gomoncli/public_html/app/system_prompt.txt
```

### Крок 5: Digital Asset Links (Google Play)

```bash
mkdir -p /home/gomoncli/public_html/.well-known
cat > /home/gomoncli/public_html/.well-known/assetlinks.json << 'EOF'
[
    {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.gomonclinic.www.twa",
            "sha256_cert_fingerprints": [
                "B2:9C:C6:35:F1:7F:58:DB:0A:56:84:23:D8:31:F3:EB:CA:1E:40:AE:55:86:31:E5:ED:A6:B0:69:9A:EC:55:0F",
                "12:D7:91:31:33:F0:17:ED:31:6E:BD:8A:19:52:3E:03:E3:FF:BE:A8:69:8A:D5:91:3A:B9:16:AF:9B:75:56:C0"
            ]
        }
    }
]
EOF
```

### Крок 6: SW cache bump

```bash
# Обов'язково після всіх змін
sed -i 's/const CACHE = "gomon-[^"]*"/const CACHE = "gomon-YYYY-MM-DDa"/' /home/gomoncli/public_html/app/sw.js
# Замінити YYYY-MM-DD на поточну дату
```

### Крок 7: Перезапуск сервісів

```bash
# Gunicorn
pkill -9 -f gunicorn
sleep 3
bash /home/gomoncli/zadarma/check_flask.sh

# Bot
pkill -f "python3.*bot.py"
sleep 2
cd /home/gomoncli/zadarma && nohup python3 bot.py >> bot.log 2>&1 &

# Перевірка
sleep 5
curl -s http://127.0.0.1:5001/api/health
```

### Крок 8: Redirect старого домену

В LiteSpeed або .htaccess для gomonclinic.com:
```
RewriteEngine On
RewriteCond %{HTTP_HOST} gomonclinic\.com [NC]
RewriteRule ^(.*)$ https://www.drgomon.com/$1 [R=301,L]
```

### Крок 9: Google Play — новий реліз

1. Оновити `twa-manifest.json`:
   ```json
   "host": "www.drgomon.com",
   "fullScopeUrl": "https://www.drgomon.com/app/"
   ```
2. Згенерувати новий AAB через PWABuilder з новим доменом
3. Збільшити versionCode: 2
4. Upload AAB в Google Play Console → Production release

### Крок 10: Зовнішні сервіси

- [ ] Google Ads: оновити конверсії (домен у тегах)
- [ ] Google Merchant: оновити feed URL
- [ ] Google Search Console: додати новий домен
- [ ] Google Analytics: додати домен або залишити той самий ID
- [ ] Instagram: оновити лінк в біо
- [ ] Telegram канал: оновити лінки в описі
- [ ] Telegram бот: оновити лінки (автоматично через скрипт вище)
- [ ] WLaunch: перевірити чи є посилання на старий домен
- [ ] SMS шаблони: перевірити WebOTP `@www.drgomon.com #code`

---

## Перевірка після міграції

```bash
# API
curl -s https://www.drgomon.com/api/health

# assetlinks.json
curl -s https://www.drgomon.com/.well-known/assetlinks.json

# manifest.json
curl -s https://www.drgomon.com/app/manifest.json | grep start_url

# SW
curl -s https://www.drgomon.com/app/sw.js | head -3

# Privacy Policy
curl -sI https://www.drgomon.com/privacy-policy.html | head -3

# Merchant feed
curl -sI https://www.drgomon.com/merchant-feed.xml | head -3

# Redirect старого домену
curl -sI https://www.gomonclinic.com/app/ | head -5
# Має бути: 301 → https://www.drgomon.com/app/

# Google Calendar feeds (ключі ті самі)
curl -s "https://www.drgomon.com/api/admin/calendar.ics?key=rtsqIeZt6zJICZOIHOQW545DYI3sRxajum-oGL3EEnw" | head -5
```

---

## Що НЕ змінюється

- Package name: `com.gomonclinic.www.twa` (залишається, не впливає на юзерів)
- Keystore: той самий
- SHA-256 fingerprints: ті самі
- БД: users.db, otp_sessions.db, feed.db — без змін
- TG bot token: той самий
- WLaunch API key: той самий
- SMS Fly credentials: ті самі
- Google Ads ID: `AW-719653819` — той самий
- Google Analytics: `G-8FC2X4SHKE` — той самий (або додати новий property)

---

## Час виконання

| Крок | Час |
|------|-----|
| DNS + SSL | 10-30 хв (залежить від провайдера) |
| Скрипт міграції (кроки 2-7) | 5 хв |
| Redirect старого домену | 5 хв |
| Новий AAB + Play Store release | 15 хв |
| Зовнішні сервіси | 20 хв |
| Перевірка | 10 хв |
| **Всього** | **~1 година** |

---

## Rollback (якщо щось пішло не так)

```bash
# Повернути старий домен
cd /home/gomoncli/zadarma
sed -i "s|drgomon.com|gomonclinic.com|g" pwa_api.py notifier.py bot.py

cd /home/gomoncli/public_html
sed -i "s|drgomon.com|gomonclinic.com|g" app/manifest.json app/sw.js app/index.html app/gomon-chat.js gomon-widget.js go.html privacy-policy.html merchant-feed.xml sitepro/a188dd94d37a0374c81c636d09cd1f05.php promos.php sitepro/prices.php sitepro/modal_prices.php

# Перезапуск
pkill -9 -f gunicorn; sleep 3; bash /home/gomoncli/zadarma/check_flask.sh
pkill -f bot.py; sleep 2; cd /home/gomoncli/zadarma && nohup python3 bot.py >> bot.log 2>&1 &
```
