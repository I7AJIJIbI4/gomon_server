<?php
/**
 * callback_request_handler.php - Обробка заявки на зворотній зв'язок
 * Розташування: /home/gomoncli/public_html/callback_request_handler.php
 * 
 * Викликається з zadarma_ivr_webhook.php при натисканні відповідного DTMF.
 * 
 * Що робить:
 * 1. Шукає caller_id в SQLite базі clients (user_db)
 * 2. Відправляє персоналізоване SMS калеру через SMSFly
 * 3. Відправляє Telegram-сповіщення спеціалісту з інформацією про клієнта
 */

// Конфігурація
$callback_config = [
    // SMSFly
    'sms_url'      => 'http://sms-fly.com/api/api.php',
    'sms_login'    => '380933297777',
    'sms_password' => 'pJYAWmZpWOvUozqAUvsTaBjxTpu9oJEk',
    
    // Telegram сповіщення
    'tg_bot_token' => 'YOUR_TELEGRAM_BOT_TOKEN',
    'tg_chat_id'   => '573368771',
    
    // SQLite база
    'db_path'      => '/home/gomoncli/zadarma/users.db',
    
    // Лог
    'log_file'     => '/home/gomoncli/zadarma/callback_requests.log'
];


function callbackLog($message) {
    global $callback_config;
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents(
        $callback_config['log_file'],
        "[$timestamp] $message\n",
        FILE_APPEND | LOCK_EX
    );
}


function formatPhoneForSMS($phone) {
    $digits = preg_replace('/[^\d]/', '', $phone);
    if (substr($digits, 0, 3) === '380' && strlen($digits) === 12) return $digits;
    if (substr($digits, 0, 1) === '0' && strlen($digits) === 10) return '38' . $digits;
    if (substr($digits, 0, 2) === '80' && strlen($digits) === 11) return '3' . $digits;
    return '380' . $digits;
}


function normalizePhoneForDB($phone) {
    return preg_replace('/[^\d]/', '', $phone);
}


function lookupClient($caller_id) {
    /**
     * Шукає клієнта в SQLite базі за номером телефону.
     * Повертає масив з даними або null.
     */
    global $callback_config;
    
    $db_path = $callback_config['db_path'];
    if (!file_exists($db_path)) {
        callbackLog("❌ БД не знайдена: $db_path");
        return null;
    }
    
    try {
        $db = new SQLite3($db_path, SQLITE3_OPEN_READONLY);
        $phone_norm = normalizePhoneForDB($caller_id);
        
        // Точний збіг
        $stmt = $db->prepare('SELECT id, first_name, last_name, phone, last_service, last_visit, visits_count FROM clients WHERE phone = :phone LIMIT 1');
        $stmt->bindValue(':phone', $phone_norm, SQLITE3_TEXT);
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($row) {
            $db->close();
            callbackLog("✅ Клієнт знайдений (точний): {$row['first_name']} {$row['last_name']} ({$row['phone']})");
            return $row;
        }
        
        // Пошук за останніми 9 цифрами
        $last9 = substr($phone_norm, -9);
        $pattern = '%' . $last9 . '%';
        
        $stmt2 = $db->prepare('SELECT id, first_name, last_name, phone, last_service, last_visit, visits_count FROM clients WHERE phone LIKE :pattern LIMIT 1');
        $stmt2->bindValue(':pattern', $pattern, SQLITE3_TEXT);
        $result2 = $stmt2->execute();
        $row2 = $result2->fetchArray(SQLITE3_ASSOC);
        
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
    /**
     * Відправляє SMS калеру через SMSFly.
     * Персоналізоване для відомих клієнтів, загальне для нових.
     */
    global $callback_config;
    
    $smsPhone = formatPhoneForSMS($caller_id);
    
    if ($client && !empty($client['first_name']) && $client['first_name'] !== 'Клієнт') {
        $name = $client['first_name'];
        $message = "$name, дякуємо за дзвінок! Запис: ig.me/m/dr.gomon | t.me/DrGomonCosmetology";
    } else {
        $message = "Dr.Gomon - дякуємо за звернення! Запис: ig.me/m/dr.gomon | t.me/DrGomonCosmetology";
    }
    
    callbackLog("📱 SMS -> $smsPhone: $message");
    
    $data = [
        'login'      => $callback_config['sms_login'],
        'password'   => $callback_config['sms_password'],
        'message'    => $message,
        'recipients' => $smsPhone,
        'format'     => 'json'
    ];
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $callback_config['sms_url']);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlError = curl_error($ch);
    curl_close($ch);
    
    if ($curlError) {
        callbackLog("❌ SMS CURL Error: $curlError");
        return false;
    }
    
    callbackLog("📱 SMS Response: HTTP $httpCode, Body: $response");
    
    if ($httpCode === 200) {
        $result = json_decode($response, true);
        if ($result && isset($result['result']) && $result['result'] === 'ok') {
            callbackLog("✅ SMS відправлено");
            return true;
        }
    }
    
    callbackLog("❌ SMS не відправлено");
    return false;
}


function sendCallbackTelegram($caller_id, $client) {
    /**
     * Відправляє Telegram-сповіщення спеціалісту.
     * Для відомих клієнтів — повна інформація (ім'я, остання послуга, візити).
     * Для нових — тільки номер.
     */
    global $callback_config;
    
    $now = date('H:i d.m.Y');
    
    if ($client && !empty($client['first_name']) && $client['first_name'] !== 'Клієнт') {
        $text = "📞 Заявка на зворотній зв'язок\n"
              . "👤 {$client['first_name']} {$client['last_name']}\n"
              . "📱 $caller_id\n"
              . "🕐 $now\n"
              . "━━━━━━━━━━━━━";
        
        if (!empty($client['visits_count']) && $client['visits_count'] > 0) {
            $text .= "\nВізитів: {$client['visits_count']}";
        }
        if (!empty($client['last_service'])) {
            $text .= "\nОстання процедура: {$client['last_service']}";
        }
        if (!empty($client['last_visit'])) {
            $text .= "\nОстанній візит: {$client['last_visit']}";
        }
    } else {
        $text = "📞 Заявка на зворотній зв'язок\n"
              . "👤 Новий клієнт\n"
              . "📱 $caller_id\n"
              . "🕐 $now";
    }
    
    callbackLog("📨 Telegram: " . str_replace("\n", " | ", $text));
    
    $url = "https://api.telegram.org/bot{$callback_config['tg_bot_token']}/sendMessage";
    $payload = json_encode([
        'chat_id' => $callback_config['tg_chat_id'],
        'text'    => $text
    ]);
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $success = $httpCode === 200;
    callbackLog($success ? "✅ Telegram відправлено" : "❌ Telegram HTTP $httpCode");
    return $success;
}


function handleCallbackRequest($caller_id) {
    /**
     * Головна функція — викликається з zadarma_ivr_webhook.php
     * при натисканні DTMF для заявки на зворотній зв'язок.
     * 
     * @param string $caller_id — номер того, хто дзвонить
     * @return array — IVR response для Zadarma
     */
    callbackLog("📞 === НОВА ЗАЯВКА від $caller_id ===");
    
    // 1. Lookup клієнта
    $client = null;
    if ($caller_id && strpos($caller_id, 'Anonymous') === false) {
        $client = lookupClient($caller_id);
    }
    
    // 2. SMS калеру (якщо номер не прихований)
    $sms_sent = false;
    if ($caller_id && strpos($caller_id, 'Anonymous') === false) {
        $sms_sent = sendCallbackSMS($caller_id, $client);
    }
    
    // 3. Telegram сповіщення спеціалісту — ЗАВЖДИ
    sendCallbackTelegram($caller_id ?: 'Прихований номер', $client);
    
    callbackLog("📞 === ЗАЯВКА ОБРОБЛЕНА (SMS: " . ($sms_sent ? 'OK' : 'FAIL') . ") ===\n");
    
    // 4. IVR відповідь — програти повідомлення і покласти слухавку
    return [
        'ivr_say' => [
            'text'     => 'Дякуємо! Ми надішлемо вам повідомлення з контактами і зв\'яжемось найближчим часом.',
            'language' => 'ua'
        ],
        'hangup' => true
    ];
}
?>
