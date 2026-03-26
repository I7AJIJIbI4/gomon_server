<?php
// zadarma_ivr_webhook.php - ВИПРАВЛЕНА версія з правильним SMS API
header('Content-Type: application/json; charset=utf-8');

if (isset($_GET['zd_echo'])) {
    exit($_GET['zd_echo']);
}

// ВИПРАВЛЕНА конфігурація
$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',      // Правильні ключі
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET',   // Правильні ключі
    'main_phone' => '0733103110',
    'gate_number' => '0930063585',
    'door_number' => '0933297777',  // Замініть на реальний!
    'log_file' => '/home/gomoncli/zadarma/ivr_webhook.log',
    
    'internal_numbers' => [
        '101' => ['name' => 'Хвіртка', 'action' => 'open_door', 'target' => '0933297777'],
        '102' => ['name' => 'Ворота', 'action' => 'open_gate', 'target' => '0930063585'],
        '103' => ['name' => 'SMS Тригер', 'action' => 'send_sms', 'target' => null]
    ],
    
    // SMS конфігурація - ЗАМІНІТЬ НА РЕАЛЬНІ НОМЕРИ!
    'sms_config' => [
        'recipients' => [
            '380933297777',  // Замініть на реальний номер!
            // '380501234567'   // Додайте інші номери
        ],
        'message_template' => 'УВАГА! SMS тригер з клініки Гомона. Час: {time}. Дзвінок від: {caller_id}'
    ]
];

function writeLog($message) {
    global $config;
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($config['log_file'], "[$timestamp] $message\n", FILE_APPEND | LOCK_EX);
}

// GET запит - статус
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    echo json_encode([
        'status' => 'active',
        'message' => 'Gomonclinic IVR Webhook (FIXED SMS)',
        'version' => '3.1-fixed',
        'time' => date('Y-m-d H:i:s'),
        'internal_numbers' => [
            '101' => 'Хвіртка → callback',
            '102' => 'Ворота → callback', 
            '103' => 'SMS тригер → відправка SMS'
        ]
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

// POST запит - webhook події
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);
    
    if (!$data) {
        $data = $_POST;
    }
    
    writeLog("Webhook received: " . json_encode($data));
    
    $event = $data['event'] ?? '';
    $caller_id = $data['caller_id'] ?? 'Unknown';
    $internal = $data['internal'] ?? '';
    
    writeLog("Event: $event, Caller: $caller_id, Internal: $internal");
    
    // Обробка internal дзвінків
    if ($event === 'NOTIFY_INTERNAL' && isset($config['internal_numbers'][$internal])) {
        $internal_config = $config['internal_numbers'][$internal];
        $name = $internal_config['name'];
        $action = $internal_config['action'];
        
        writeLog("SPECIAL INTERNAL: $name від $caller_id (internal: $internal)");
        
        switch ($action) {
            case 'open_gate':
            case 'open_door':
                $target = $internal_config['target'];
                $success = makeZadarmaCallback($target, $config);
                writeLog($success ? "✅ $name callback успішний" : "❌ $name callback помилка");
                break;
                
            case 'send_sms':
                $success = sendSMSTrigger($caller_id, $config);
                writeLog($success ? "✅ SMS тригер успішний" : "❌ SMS тригер помилка");
                break;
        }
    }
    
    echo json_encode(['status' => 'ok']);
    exit;
}

// Callback функція (працює)
function makeZadarmaCallback($toNumber, $config) {
    writeLog("Making callback to: $toNumber");
    
    $method = '/v1/request/callback/';
    $params = [
        'from' => $config['main_phone'],
        'to' => $toNumber,
        'format' => 'json'
    ];
    
    ksort($params);
    $paramsString = http_build_query($params);
    $stringToSign = $method . $paramsString . md5($paramsString);
    $signature = base64_encode(hash_hmac('sha1', $stringToSign, $config['zadarma_secret'], false));
    
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/x-www-form-urlencoded'
    ];
    
    $url = 'https://api.zadarma.com' . $method . '?' . $paramsString;
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    writeLog("Callback response: HTTP $httpCode, Body: $response");
    
    if ($httpCode === 200) {
        $result = json_decode($response, true);
        return ($result['status'] ?? '') === 'success';
    }
    
    return false;
}

// SMS тригер
function sendSMSTrigger($caller_id, $config) {
    writeLog("SMS trigger activated by: $caller_id");
    
    $sms_config = $config['sms_config'];
    $recipients = $sms_config['recipients'];
    $message = str_replace(
        ['{time}', '{caller_id}'],
        [date('Y-m-d H:i:s'), $caller_id],
        $sms_config['message_template']
    );
    
    writeLog("SMS message: $message");
    writeLog("SMS recipients: " . implode(', ', $recipients));
    
    $success_count = 0;
    foreach ($recipients as $recipient) {
        if (sendZadarmaSMS($recipient, $message, $config)) {
            $success_count++;
        }
    }
    
    writeLog("SMS trigger completed: $success_count/" . count($recipients) . " successful");
    return $success_count > 0;
}

// ВИПРАВЛЕНА SMS функція
function sendZadarmaSMS($to, $message, $config) {
    writeLog("Sending SMS to: $to");
    
    $method = '/v1/sms/send/';
    
    // ПРАВИЛЬНІ параметри згідно документації
    $params = [
        'number' => $to,
        'message' => $message,
        'sender' => $config['main_phone']  // Використовуємо наш віртуальний номер як відправника
    ];
    
    ksort($params);
    $paramsString = http_build_query($params);
    $stringToSign = $method . $paramsString . md5($paramsString);
    $signature = base64_encode(hash_hmac('sha1', $stringToSign, $config['zadarma_secret'], true));
    
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/x-www-form-urlencoded'
    ];
    
    $url = 'https://api.zadarma.com' . $method;
    
    writeLog("SMS API: $url");
    writeLog("SMS params: $paramsString");
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $paramsString);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    writeLog("SMS to $to: HTTP $httpCode, Response: $response");
    
    if ($httpCode === 200) {
        $result = json_decode($response, true);
        $success = ($result['status'] ?? '') === 'success';
        
        if ($success) {
            $cost = $result['cost'] ?? 0;
            $currency = $result['currency'] ?? 'USD';
            writeLog("✅ SMS успішно відправлено! Вартість: $cost $currency");
        }
        
        return $success;
    }
    
    return false;
}

writeLog("Webhook script completed");
?>
