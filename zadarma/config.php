<?php
/**
 * config.php — Shared credentials for PHP scripts
 * Розташування: /home/gomoncli/zadarma/config.php
 */

// Telegram
define('TG_BOT_TOKEN',   'YOUR_TELEGRAM_BOT_TOKEN');
define('TG_ADMIN_CHAT',  '573368771');   // ADMIN_USER_ID (особистий чат)
define('TG_CALLBACK_CHAT', '7930079513'); // DrGomonCosmetology (+380733103110)

// SMS-Fly API v2
define('SMS_FLY_API_KEY',    'pJYAWmZpWOvUozqAUvsTaBjxTpu9oJEk');
define('SMS_FLY_API_URL',    'https://sms-fly.ua/api/v2/api.php');
define('SMS_FLY_SENDER',     'Dr. Gomon');

// Zadarma
define('ZADARMA_API_KEY',    'YOUR_ZADARMA_KEY');
define('ZADARMA_API_SECRET', 'YOUR_ZADARMA_SECRET');
define('ZADARMA_MAIN_PHONE', '0733103110');

// Paths
define('DB_PATH',   '/home/gomoncli/zadarma/users.db');
define('LOG_DIR',   '/home/gomoncli/zadarma/');
