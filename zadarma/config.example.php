<?php
/**
 * config.example.php — Template for zadarma/config.php (NOT in git — see .gitignore)
 * Розташування: /home/gomoncli/zadarma/config.php
 * Скопіювати цей файл в config.php і заповнити реальними значеннями на сервері.
 */

// Telegram
define('TG_BOT_TOKEN',   'YOUR_TELEGRAM_BOT_TOKEN');
define('TG_ADMIN_CHAT',  'YOUR_ADMIN_CHAT_ID');
define('TG_CALLBACK_CHAT', 'YOUR_CALLBACK_CHAT_ID');

// SMS-Fly API v2
define('SMS_FLY_API_KEY',    'YOUR_SMS_FLY_API_KEY');
define('SMS_FLY_API_URL',    'https://sms-fly.ua/api/v2/api.php');
define('SMS_FLY_SENDER',     'Dr. Gomon');

// Zadarma
define('ZADARMA_API_KEY',    'YOUR_ZADARMA_KEY');
define('ZADARMA_API_SECRET', 'YOUR_ZADARMA_SECRET');
define('ZADARMA_MAIN_PHONE', '0733103110');

// Paths
define('DB_PATH',   '/home/gomoncli/zadarma/users.db');
define('LOG_DIR',   '/home/gomoncli/zadarma/');
