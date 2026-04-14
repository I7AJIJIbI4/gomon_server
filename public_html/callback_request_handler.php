<?php
/**
 * callback_request_handler.php - Обробка заявки на зворотній зв'язок
 * Розташування: /home/gomoncli/public_html/callback_request_handler.php
 *
 * Що робить:
 * 1. Шукає caller_id в SQLite (clients + services_json)
 * 2. Відправляє SMS калеру
 * 3. Відправляє Telegram: клікабельний телефон + перелік послуг з датами
 */

require_once '/home/gomoncli/zadarma/config.php';

define('SMS_TEXT_KNOWN_CLIENT',   'Вітаємо, {name}! Для швидкого запису: Telegram: flyl.link/DGC · Direct: flyl.link/IG');
define('SMS_TEXT_UNKNOWN_CLIENT', 'Вітаємо! Для швидкого запису: Telegram: flyl.link/DGC · Direct: flyl.link/IG');

$callback_config = [
    'sms_url'      => SMS_FLY_API_URL,
    'sms_api_key'  => SMS_FLY_API_KEY,
    'sms_source'   => SMS_FLY_SENDER,

    'tg_bot_token' => TG_BOT_TOKEN,
    'tg_chat_id'   => TG_CALLBACK_CHAT,

    'db_path'      => DB_PATH,
    'log_file'     => LOG_DIR . 'callback_requests.log',
];


function lookup_tg_user_by_phone(string $phone): ?array {
    $db_path = '/home/gomoncli/zadarma/users.db';
    if (!file_exists($db_path)) return null;
    try {
        $db = new SQLite3($db_path, SQLITE3_OPEN_READONLY);
        $last9 = substr(preg_replace('/[^\d]/', '', $phone), -9);
        $stmt = $db->prepare("SELECT telegram_id, username FROM users WHERE phone LIKE :p LIMIT 1");
        $stmt->bindValue(':p', '%' . $last9, SQLITE3_TEXT);
        $res = $stmt->execute();
        $row = $res ? $res->fetchArray(SQLITE3_ASSOC) : null;
        $db->close();
        return $row ?: null;
    } catch (Exception $e) { return null; }
}


function callbackLog($message) {
    global $callback_config;
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($callback_config['log_file'], "[$timestamp] $message\n", FILE_APPEND | LOCK_EX);
}


/** Повертає номер у форматі +380XXXXXXXXX */
function formatPhoneE164($phone) {
    $d = preg_replace('/[^\d]/', '', $phone);
    if (substr($d, 0, 3) === '380' && strlen($d) === 12) return '+' . $d;
    if (substr($d, 0, 1) === '0'   && strlen($d) === 10) return '+38' . $d;
    if (substr($d, 0, 2) === '80'  && strlen($d) === 11) return '+3' . $d;
    return '+380' . $d;
}


function formatPhoneForSMS($phone) {
    return ltrim(formatPhoneE164($phone), '+');
}


function normalizePhoneForDB($phone) {
    return preg_replace('/[^\d]/', '', $phone);
}


/** Перетворює YYYY-MM-DD → DD.MM.YYYY */
function fmtDate($date) {
    $parts = explode('-', $date);
    return count($parts) === 3 ? "{$parts[2]}.{$parts[1]}.{$parts[0]}" : $date;
}


function lookupClient($caller_id) {
    global $callback_config;

    $db_path = $callback_config['db_path'];
    if (!file_exists($db_path)) {
        callbackLog("❌ БД не знайдена: $db_path");
        return null;
    }

    try {
        $db         = new SQLite3($db_path, SQLITE3_OPEN_READONLY);
        $phone_norm = normalizePhoneForDB($caller_id);

        $stmt = $db->prepare(
            'SELECT id, first_name, last_name, phone, last_service, last_visit, visits_count, services_json
             FROM clients WHERE phone = :phone LIMIT 1'
        );
        $stmt->bindValue(':phone', $phone_norm, SQLITE3_TEXT);
        $row = $stmt->execute()->fetchArray(SQLITE3_ASSOC);

        if ($row) {
            $db->close();
            callbackLog("✅ Клієнт знайдений (точний): {$row['first_name']} {$row['last_name']} ({$row['phone']})");
            return $row;
        }

        $last9   = substr($phone_norm, -9);
        $pattern = '%' . $last9 . '%';
        $stmt2   = $db->prepare(
            'SELECT id, first_name, last_name, phone, last_service, last_visit, visits_count, services_json
             FROM clients WHERE phone LIKE :pattern LIMIT 1'
        );
        $stmt2->bindValue(':pattern', $pattern, SQLITE3_TEXT);
        $row2 = $stmt2->execute()->fetchArray(SQLITE3_ASSOC);
        $db->close();

        if ($row2) {
            callbackLog("✅ Клієнт знайдений (патерн): {$row2['first_name']} {$row2['last_name']} ({$row2['phone']})");
            return $row2;
        }

        callbackLog("ℹ️ Клієнта з номером $caller_id не знайдено в базі");
        return null;

    } catch (Exception $e) {
        callbackLog("❌ Помилка БД: " . $e->getMessage());
        return null;
    }
}


function sendCallbackSMS($caller_id, $client) {
    global $callback_config;

    $smsPhone = formatPhoneForSMS($caller_id);
    $message  = ($client && !empty($client['first_name']) && $client['first_name'] !== 'Клієнт')
        ? str_replace('{name}', $client['first_name'], SMS_TEXT_KNOWN_CLIENT)
        : SMS_TEXT_UNKNOWN_CLIENT;

    callbackLog("📱 SMS -> $smsPhone: $message");

    $request_data = [
        'auth'   => ['key' => $callback_config['sms_api_key']],
        'action' => 'SENDMESSAGE',
        'data'   => [
            'recipient'  => $smsPhone,
            'channels'   => ['sms'],
            'sms'        => ['source' => $callback_config['sms_source'], 'text' => $message, 'start_time' => 'AUTO']
        ]
    ];

    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $callback_config['sms_url'],
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($request_data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json; charset=utf-8'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_SSL_VERIFYPEER => true,
    ]);
    $response  = curl_exec($ch);
    $httpCode  = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlError = curl_error($ch);
    curl_close($ch);

    if ($curlError) { callbackLog("❌ SMS CURL Error: $curlError"); return false; }
    callbackLog("📱 SMS Response: HTTP $httpCode, Body: $response");

    if ($httpCode === 200) {
        $result = json_decode($response, true);
        if (isset($result['success']) && $result['success'] == 1) {
            callbackLog("✅ SMS відправлено");
            return true;
        }
        callbackLog("❌ SMS error: " . ($result['error']['description'] ?? json_encode($result)));
    }
    return false;
}


function sendCallbackTelegram($caller_id, $client) {
    global $callback_config;

    $now        = date('H:i d.m.Y');
    $phone_e164 = formatPhoneE164($caller_id);
    $phone_link = '<a href="tel:' . $phone_e164 . '">' . $phone_e164 . '</a>';
    $tg_user    = lookup_tg_user_by_phone($caller_id);
    if ($tg_user && !empty($tg_user['username'])) {
        $phone_link .= ' · <a href="https://t.me/' . htmlspecialchars($tg_user['username'], ENT_XML1) . '">@' . htmlspecialchars($tg_user['username'], ENT_XML1) . '</a>';
    } elseif ($tg_user && !empty($tg_user['telegram_id'])) {
        $phone_link .= ' · <a href="tg://user?id=' . (int)$tg_user['telegram_id'] . '">Telegram</a>';
    }

    if ($client && !empty($client['first_name']) && $client['first_name'] !== 'Клієнт') {
        $name = htmlspecialchars("{$client['first_name']} {$client['last_name']}", ENT_XML1);
        $text = "📞 <b>Заявка на зворотній зв'язок</b>\n"
              . "👤 {$name}\n"
              . "📱 {$phone_link}\n"
              . "🕐 {$now}";

        if (!empty($client['visits_count']) && $client['visits_count'] > 0) {
            $text .= "\n━━━━━━━━━━━━━\n"
                   . "Всього візитів: <b>{$client['visits_count']}</b>";
        }

        $services = json_decode($client['services_json'] ?? '[]', true);
        if (!empty($services)) {
            $text .= "\n\n💉 <b>Процедури:</b>";
            foreach ($services as $s) {
                $date_fmt = fmtDate($s['date'] ?? '');
                $svc      = htmlspecialchars($s['service'] ?? '', ENT_XML1);
                $text    .= "\n• {$date_fmt} — {$svc}";
            }
        } elseif (!empty($client['last_visit'])) {
            $text .= "\nОстанній візит: " . fmtDate($client['last_visit']);
        }
    } else {
        $text = "📞 <b>Заявка на зворотній зв'язок</b>\n"
              . "👤 Новий клієнт\n"
              . "📱 {$phone_link}\n"
              . "🕐 {$now}";
    }

    callbackLog("📨 Telegram: " . str_replace("\n", " | ", strip_tags($text)));

    $url     = "https://api.telegram.org/bot{$callback_config['tg_bot_token']}/sendMessage";
    $payload = json_encode([
        'chat_id'    => $callback_config['tg_chat_id'],
        'text'       => $text,
        'parse_mode' => 'HTML',
    ]);

    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $url,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
    ]);
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpCode !== 200) {
        callbackLog("❌ Telegram HTTP $httpCode: $response");
        return false;
    }
    callbackLog("✅ Telegram відправлено");
    return true;
}


function handleCallbackRequest($caller_id) {
    callbackLog("📞 === НОВА ЗАЯВКА від $caller_id ===");

    $client = null;
    if ($caller_id && strpos($caller_id, 'Anonymous') === false) {
        $client = lookupClient($caller_id);
    }

    $sms_sent = sendCallbackSMS($caller_id, $client);

    sendCallbackTelegram($caller_id ?: 'Прихований номер', $client);

    callbackLog("📞 === ЗАЯВКА ОБРОБЛЕНА (SMS: " . ($sms_sent ? "відправлено" : "помилка") . ") ===\n");

    return [
        'ivr_say' => [
            'text'     => "Дякуємо! Ми надішлемо вам повідомлення з контактами і зв'яжемось найближчим часом.",
            'language' => 'ua'
        ],
        'hangup' => true
    ];
}
?>
