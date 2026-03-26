<?php
// ОНОВЛЕНА СИСТЕМА з IVR + Telegram Bot Support
header('Content-Type: application/json; charset=utf-8');

if (isset($_GET['zd_echo'])) {
    exit($_GET['zd_echo']);
}

$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET',
    'main_phone' => '0733103110',
    'log_file' => '/home/gomoncli/zadarma/ivr_webhook.log',

    // Номер лікаря для переадресації (кнопка 3 в новому IVR)
    'doctor_phone' => '380996093860',

    'internal_numbers' => [
        // === Новий клієнтський IVR (кнопки 1/2/3) ===
        // Кнопка 1 — обидва можливих internal покриті (з'ясується після першого тест-дзвінка)
        '104' => ['name' => 'IVR Кнопка 1 — Callback (direct ext)', 'action' => 'callback_request', 'target' => null],
        '204' => ['name' => 'IVR Кнопка 1 — Callback (via menu)', 'action' => 'callback_request', 'target' => null],
        // Кнопка 2 → callback request (SMS + Telegram лікарю)
        '106' => ['name' => 'IVR Кнопка 2 — Callback (direct ext)', 'action' => 'callback_request', 'target' => null],
        '206' => ['name' => 'IVR Кнопка 2 — Callback (via menu)', 'action' => 'callback_request', 'target' => null],
        // Кнопка 3 → дзвінок лікарю (обидва варіанти)
        '105' => ['name' => 'IVR Кнопка 3 — Лікар (direct ext)', 'action' => 'forward_to_doctor', 'target' => null],
        '205' => ['name' => 'IVR Кнопка 3 — Лікар (via menu)', 'action' => 'forward_to_doctor', 'target' => null],

    ],

    'telegram_config' => [
        'bot_token' => 'YOUR_TELEGRAM_BOT_TOKEN',
        'chat_id' => '573368771'
    ]
];

function writeLog($message) {
    global $config;
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($config['log_file'], "[$timestamp] $message\n", FILE_APPEND | LOCK_EX);
}

function normalizePhoneNumber($phone) {
    $phone = preg_replace('/[^\d]/', '', $phone);
    if (substr($phone, 0, 3) === '380') {
        return substr($phone, 2);
    } elseif (substr($phone, 0, 2) === '80') {
        return '0' . substr($phone, 2);
    }
    return $phone;
}

function formatPhoneForSMS($phone) {
    $phone = preg_replace('/[^\d]/', '', $phone);

    if (substr($phone, 0, 3) === '380') {
        return $phone;
    } elseif (substr($phone, 0, 2) === '80') {
        return '3' . $phone;
    } elseif (substr($phone, 0, 1) === '0') {
        return '38' . $phone;
    }

    return '380' . $phone;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    echo json_encode([
        'status' => 'active',
        'message' => '🚀 FINAL WORKING SYSTEM + TELEGRAM BOT',
        'version' => '18.0-TELEGRAM-INTEGRATION',
        'sms_source' => 'Dr. Gomon (з пробілом)',
        'features' => [
            'door_control' => 'Zadarma Callback ✅',
            'gate_control' => 'Zadarma Callback ✅',
            'sms_delivery' => 'SMS-Fly API ✅',
            'telegram_backup' => 'Available ✅',
            'telegram_bot_integration' => 'НОВИНКА ✅'
        ]
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents('php://input'), true) ?: $_POST;

    writeLog("WEBHOOK RECEIVED: " . json_encode($data));

    $event = $data['event'] ?? '';
    $caller_id = normalizePhoneNumber($data['caller_id'] ?? 'Unknown');
    $internal = $data['internal'] ?? '';

    // ДІАГНОСТИКА: лог для з'ясування internal-номерів
    if ($event === 'NOTIFY_INTERNAL') {
        writeLog("🔍 NOTIFY_INTERNAL: internal='$internal', caller='$caller_id' — " .
            (isset($config['internal_numbers'][$internal])
                ? "відомий: " . $config['internal_numbers'][$internal]['name']
                : "НЕВІДОМИЙ — додати до internal_numbers якщо потрібно"));
    }

    // ОБРОБКА РІЗНИХ ТИПІВ ПОДІЙ
    if ($event === 'NOTIFY_INTERNAL') {
        handleCorrectSource($internal, $caller_id);
    } elseif ($event === 'NOTIFY_START' || $event === 'NOTIFY_END') {
        // НОВИНКА: Обробка подій для телеграм бота
        handleTelegramBotEvent($data);
    } else {
        writeLog("ℹ️ Event $event ignored");
        echo json_encode(['status' => 'ok']);
    }
}

// НОВИНКА: Функція для обробки подій телеграм бота
function handleTelegramBotEvent($data) {
    writeLog("🤖 TELEGRAM BOT EVENT: " . json_encode($data));
    
    $event = $data['event'] ?? '';
    $pbxCallId = $data['pbx_call_id'] ?? '';
    $disposition = $data['disposition'] ?? '';
    
    // Викликаємо Python скрипт для обробки
    if (in_array($event, ['NOTIFY_START', 'NOTIFY_END'])) {
        $pythonScript = '/home/gomoncli/zadarma/process_webhook.py';
        $jsonData = escapeshellarg(json_encode($data));
        
        $command = "cd /home/gomoncli/zadarma && python3 $pythonScript $jsonData 2>&1";
        
        writeLog("🐍 Executing Python: $command");
        
        $output = shell_exec($command);
        $exitCode = shell_exec("echo $?");
        
        writeLog("📤 Python output: " . ($output ?: 'No output'));
        writeLog("📊 Python exit code: " . ($exitCode ?: 'Unknown'));
        
        if ($exitCode == 0) {
            writeLog("✅ Telegram bot event processed successfully");
        } else {
            writeLog("❌ Telegram bot event processing failed");
        }
    }
    
    echo json_encode(['status' => 'ok']);
}

// Існуюча функція IVR системи
function handleCorrectSource($internal, $caller_id) {
    global $config;

    writeLog("🚀 IVR SYSTEM: Internal $internal, Caller $caller_id");

    if (isset($config['internal_numbers'][$internal])) {
        $internal_config = $config['internal_numbers'][$internal];
        $name = $internal_config['name'];
        $action = $internal_config['action'];
        $target = $internal_config['target'];

        switch ($action) {
            case 'callback_request':
                writeLog("📞 Кнопка 1 — callback від $caller_id");
                require_once __DIR__ . '/callback_request_handler.php';
                handleCallbackRequest($caller_id);
                break;

            case 'forward_to_doctor':
                $doctor = $config['doctor_phone'];
                writeLog("👨‍⚕️ Кнопка 3 — переадресація на лікаря ($doctor) від $caller_id");
                $success = makeCallback($doctor, $config, $caller_id);
                writeLog($success ? "✅ Дзвінок лікарю ініційовано" : "❌ Помилка переадресації на лікаря");
                break;
        }
    }

    echo json_encode(['status' => 'ok']);
}

function makeCallback($toNumber, $config, $caller_id) {
    writeLog("📞 Callback: {$config['main_phone']} → $toNumber");

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

    $headers = ['Authorization: ' . $config['zadarma_key'] . ':' . $signature];
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

    writeLog("📞 Callback result: HTTP $httpCode");
    return $httpCode === 200 && strpos($response, '"status":"success"') !== false;
}

?>

