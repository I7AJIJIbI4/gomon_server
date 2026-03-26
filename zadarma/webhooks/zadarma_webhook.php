<?php
// === BOT CALLBACK ROUTER ===
// Додано для розділення IVR та Bot webhook

if (isset($_GET['zd_echo'])) exit($_GET['zd_echo']);

error_reporting(E_ALL);
ini_set('log_errors', 1);

// ПОКРАЩЕНЕ ОТРИМАННЯ ДАНИХ
$input = file_get_contents('php://input');
$data = [];

// Спробуємо JSON
if (!empty($input)) {
    $json_data = json_decode($input, true);
    if (json_last_error() === JSON_ERROR_NONE) {
        $data = $json_data;
    }
}

// Якщо JSON не спрацював, беремо POST
if (empty($data) && !empty($_POST)) {
    $data = $_POST;
}

// Детальне логування
error_log("=== ZADARMA WEBHOOK DEBUG ===");
error_log("Method: " . $_SERVER['REQUEST_METHOD']);
error_log("Content-Type: " . ($_SERVER['CONTENT_TYPE'] ?? 'not set'));
error_log("Content-Length: " . ($_SERVER['CONTENT_LENGTH'] ?? 'not set'));
error_log("Raw input: " . $input);
error_log("POST data: " . json_encode($_POST));
error_log("Final data: " . json_encode($data));

// ... решта коду залишається без змін

// Логування
error_log("Zadarma webhook received: " . json_encode($data));

// Функція визначення bot callback
function isBotCallback($data) {
    $caller = $data['caller_id'] ?? '';
    $called = $data['called_did'] ?? '';
    // ВИПРАВЛЕНА ЛОГІКА: webhook FROM=пристрій, TO=клініка
    $isBot = ((strpos($caller, '637442017') !== false || 
               strpos($caller, '930063585') !== false) &&
              (strpos($called, '733103110') !== false));
    error_log("Bot callback check: FROM=$caller, TO=$called, IS_BOT=" . ($isBot ? 'YES' : 'NO'));
    return $isBot;
}

// Якщо це bot callback завершення - передаємо в Python
if (($data['event'] ?? '') === 'NOTIFY_END' && isBotCallback($data)) {
    error_log("ROUTING TO PYTHON BOT");
    
    $json = escapeshellarg(json_encode($data));
    $command = "cd /home/gomoncli/zadarma && /usr/bin/python3 simple_webhook.py $json 2>&1";
    exec($command, $output, $returnCode);
    
    $result = implode("\n", $output);
    error_log("Python result (code $returnCode): $result");
    
    header('Content-Type: application/json');
    echo json_encode(['status' => 'bot_processed', 'result' => $result]);
    exit; // ВАЖЛИВО: припинити виконання, щоб IVR код не виконувався
}

error_log("Continuing with IVR logic...");
// webhook.php - Простий PHP webhook для shared hosting
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Логування
function writeLog($message) {
    $logFile = __DIR__ . '/logs/webhook.log';
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($logFile, "[$timestamp] $message\n", FILE_APPEND | LOCK_EX);
}

// Заголовки для JSON відповіді
header('Content-Type: application/json; charset=utf-8');

// Конфігурація
$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',    // Ваш API ключ
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET', // Ваш API секрет
    'main_phone' => '0733103110',               // Основний номер
    'gate_number' => '0996093860',              // Номер воріт
    'door_number' => '0501234567',              // Номер хвіртки (замініть на реальний)
];

// Перевірка GET запиту (валідація webhook)
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    if (isset($_GET['zd_echo'])) {
        echo $_GET['zd_echo'];
        exit;
    }
    
    echo json_encode([
        'status' => 'active',
        'message' => 'Zadarma Webhook працює',
        'time' => date('Y-m-d H:i:s')
    ]);
    exit;
}

// Обробка POST запитів
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    
    // Отримуємо дані
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);
    
    // Якщо JSON не розпарсився, пробуємо POST параметри
    if (!$data) {
        $data = $_POST;
    }
    
    writeLog("Отримано webhook: " . json_encode($data));
    
    $event = $data['event'] ?? '';
    $caller_id = $data['caller_id'] ?? 'Unknown';
    
    switch ($event) {
        case 'NOTIFY_START':
            handleCallStart($data);
            break;
            
        case 'NOTIFY_IVR':
            handleIvrResponse($data);
            break;
            
        case 'NOTIFY_END':
            handleCallEnd($data);
            break;
            
        default:
            writeLog("Невідомий тип події: $event");
            echo json_encode(['status' => 'ok']);
            break;
    }
} else {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
}

function handleCallStart($data) {
    $caller_id = $data['caller_id'] ?? 'Unknown';
    writeLog("Початок дзвінка від: $caller_id");
    
    // Відповідь з голосовим меню
    $response = [
        'ivr_say' => [
            'text' => 'Доброго дня! Ви дзвоните до системи контролю доступу. Натисніть 1 для відкриття воріт, 2 для відкриття хвіртки.',
            'language' => 'ua'
        ],
        'wait_dtmf' => [
            'timeout' => 10,
            'max_digits' => 1,
            'attempts' => 3,
            'name' => 'main_menu'
        ]
    ];
    
    echo json_encode($response);
}

function handleIvrResponse($data) {
    $caller_id = $data['caller_id'] ?? 'Unknown';
    $wait_dtmf = $data['wait_dtmf'] ?? [];
    $digits = $wait_dtmf['digits'] ?? '';
    
    writeLog("Користувач $caller_id натиснув: '$digits'");
    
    global $config;
    
    switch ($digits) {
        case '1':
            // Відкриття воріт
            writeLog("Запит на відкриття воріт від $caller_id");
            
            $success = makeZadarmaCall($config['gate_number'], $config);
            
            if ($success) {
                $message = 'Відкриваємо ворота, зачекайте будь ласка. Ворота відкриваються.';
                writeLog("✅ Ворота відкрито для $caller_id");
            } else {
                $message = 'Вибачте, виникла технічна проблема з воротами. Спробуйте пізніше.';
                writeLog("❌ Не вдалося відкрити ворота для $caller_id");
            }
            
            echo json_encode([
                'ivr_say' => [
                    'text' => $message,
                    'language' => 'ua'
                ],
                'hangup' => true
            ]);
            break;
            
        case '2':
            // Відкриття хвіртки
            writeLog("Запит на відкриття хвіртки від $caller_id");
            
            $success = makeZadarmaCall($config['door_number'], $config);
            
            if ($success) {
                $message = 'Відкриваємо хвіртку, зачекайте будь ласка. Хвіртка відкривається.';
                writeLog("✅ Хвіртка відкрита для $caller_id");
            } else {
                $message = 'Вибачте, виникла технічна проблема з хвірткою. Спробуйте пізніше.';
                writeLog("❌ Не вдалося відкрити хвіртку для $caller_id");
            }
            
            echo json_encode([
                'ivr_say' => [
                    'text' => $message,
                    'language' => 'ua'
                ],
                'hangup' => true
            ]);
            break;
            
        default:
            // Невірний вибір
            writeLog("Невірний вибір '$digits' від $caller_id");
            
            echo json_encode([
                'ivr_say' => [
                    'text' => 'Невірний вибір. Натисніть 1 для воріт або 2 для хвіртки.',
                    'language' => 'ua'
                ],
                'wait_dtmf' => [
                    'timeout' => 10,
                    'max_digits' => 1,
                    'attempts' => 2,
                    'name' => 'main_menu'
                ]
            ]);
            break;
    }
}

function handleCallEnd($data) {
    $caller_id = $data['caller_id'] ?? 'Unknown';
    $duration = $data['duration'] ?? 0;
    
    writeLog("Завершення дзвінка від $caller_id (тривалість: {$duration}с)");
    
    echo json_encode(['status' => 'ok']);
}

function makeZadarmaCall($toNumber, $config) {
    $method = '/v1/request/callback/';
    $params = [
        'from' => $config['main_phone'],
        'to' => $toNumber,
        'format' => 'json'
    ];
    
    // Сортуємо параметри
    ksort($params);
    $paramsString = http_build_query($params);
    
    // Створюємо підпис
    $stringToSign = $method . $paramsString . md5($paramsString);
    $signature = base64_encode(hash_hmac('sha1', $stringToSign, $config['zadarma_secret'], true));
    
    // Заголовки
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/x-www-form-urlencoded'
    ];
    
    // CURL запит
    $url = 'https://api.zadarma.com' . $method . '?' . $paramsString;
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    writeLog("Zadarma callback на $toNumber: HTTP $httpCode, Response: $response");
    
    if ($httpCode === 200) {
        $result = json_decode($response, true);
        return $result['status'] === 'success';
    }
    
    return false;
}
?>
