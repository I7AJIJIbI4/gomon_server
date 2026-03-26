# Dr. Gómon PWA — Інструкція по деплою
# =============================================

## Файли:
# index.html   → /home/gomoncli/public_html/app/index.html
# manifest.json → /home/gomoncli/public_html/app/manifest.json
# sw.js        → /home/gomoncli/public_html/app/sw.js
# pwa_api.py   → /home/gomoncli/zadarma/pwa_api.py

## КРОК 1 — Створити папку і завантажити файли
mkdir -p ~/public_html/app/icons
# Завантажити index.html, manifest.json, sw.js в ~/public_html/app/
# Завантажити pwa_api.py в ~/zadarma/

## КРОК 2 — Іконки (згенерувати з logo.png)
# Потрібні файли:
#   ~/public_html/app/icons/icon-192.png  (192x192)
#   ~/public_html/app/icons/icon-512.png  (512x512)
#   ~/public_html/app/icons/icon-180.png  (180x180, для Apple Touch Icon)
#
# Генерація через ImageMagick:
convert ~/public_html/logo.png -resize 192x192 ~/public_html/app/icons/icon-192.png
convert ~/public_html/logo.png -resize 512x512 ~/public_html/app/icons/icon-512.png
convert ~/public_html/logo.png -resize 180x180 ~/public_html/app/icons/icon-180.png

## КРОК 3 — Встановити залежності Flask
pip3 install flask flask-cors --user
# або якщо pip через venv:
# python3 -m pip install flask flask-cors

## КРОК 4 — Налаштувати проксі в .htaccess
# Додати в ~/public_html/.htaccess:
cat >> ~/public_html/.htaccess << 'EOF'

# PWA API proxy
RewriteRule ^api/(.*)$ http://127.0.0.1:5001/api/$1 [P,L]

# PWA app
RewriteRule ^app/(.*)$ http://127.0.0.1:5001/app/$1 [P,L]
RewriteRule ^app$ http://127.0.0.1:5001/app/ [P,L,R=301]
EOF

## КРОК 5 — Запустити Flask API
cd ~/zadarma
nohup python3 pwa_api.py > pwa_api.log 2>&1 &
echo "PID: $!"

# Перевірка:
curl http://127.0.0.1:5001/api/health

## КРОК 6 — Автозапуск через cron (якщо нема systemd)
crontab -e
# Додати рядок:
# @reboot sleep 15 && cd /home/gomoncli/zadarma && nohup python3 pwa_api.py >> pwa_api.log 2>&1 &

## КРОК 7 — HTTPS (обов'язково для PWA!)
# PWA працює ТІЛЬКИ по HTTPS. На gomonclinic.com вже є SSL — все добре.
# Перевірити: https://www.gomonclinic.com/app/

## КРОК 8 — Реєстрація Service Worker (в index.html вже є, але переконайся)
# В index.html перед </body>:
# <script>
#   if ('serviceWorker' in navigator) {
#     navigator.serviceWorker.register('/app/sw.js', {scope: '/app/'});
#   }
# </script>

## ПЕРЕВІРКА ДЕПЛОЮ:
# 1. https://www.gomonclinic.com/app/ — відкривається?
# 2. Chrome DevTools → Application → Manifest — показує іконки?
# 3. Chrome DevTools → Application → Service Workers — активний?
# 4. https://www.gomonclinic.com/api/health → {"ok": true}
# 5. На iPhone Safari → ⎙ → На початковий екран → іконка є?

## ОНОВЛЕННЯ prices.json:
# Файл вже є на сервері ~/public_html/prices.json
# API /api/prices читає його напряму — оновлення миттєве.

## ОНОВЛЕННЯ БД клієнтів:
# Cron вже є (8:00 та 23:00) — записи підтягнуться автоматично.

## ТЕСТУВАННЯ OTP БЕЗ SMS (dev mode):
# В pwa_api.py є fallback: якщо SMS не відправлено,
# відповідь містить debug_code. ПРИБРАТИ ПЕРЕД ПРОДОМ!
# Рядок: return jsonify({'ok': True, 'debug_code': code})
# Замінити на: return jsonify({'error': 'sms_failed'}), 500

## ПОСИЛАННЯ ДЛЯ КЛІЄНТІВ:
# https://www.gomonclinic.com/app/
# Можна скоротити через bit.ly або додати QR на ресепшн.
