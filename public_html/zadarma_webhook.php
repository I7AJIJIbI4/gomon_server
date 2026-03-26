<?php
header('Content-Type: application/json; charset=utf-8');

if (isset($_GET['zd_echo'])) exit($_GET['zd_echo']);

// Отримання даних
$input = file_get_contents('php://input');
$data = [];
if (!empty($input)) {
    $json_data = json_decode($input, true);
    if (json_last_error() === JSON_ERROR_NONE) {
        $data = $json_data;
    }
}
if (empty($data) && !empty($_POST)) {
    $data = $_POST;
}

error_log("Zadarma webhook: " . json_encode($data));

$config = [
    'zadarma_key'    => 'YOUR_ZADARMA_KEY',
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET',
    'main_phone'     => '0733103110',
];

// Логування у файл
function writeLog($message) {
    $logFile = '/home/gomoncli/public_html/logs/webhook.log';
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($logFile, "[$timestamp] $message\n", FILE_APPEND | LOCK_EX);
}

// Визначення тригерних дзвінків
function isInternalTriggerCall($data) {
    $called   = $data['called_did'] ?? '';
    $internal = $data['internal'] ?? '';

    $isCallbackTrigger = ($internal === '103' || strpos($called, '518196-103') !== false || strpos($called, '#518196-103') !== false);

    error_log("Trigger check: internal=$internal, Callback=$isCallbackTrigger");

    return [
        'is_trigger'  => $isCallbackTrigger,
        'is_callback' => $isCallbackTrigger,
    ];
}

// Обробка тригерів (NOTIFY_START або NOTIFY_INTERNAL)
$triggerInfo = isInternalTriggerCall($data);
$event = $data['event'] ?? '';

if (($event === 'NOTIFY_START' || $event === 'NOTIFY_INTERNAL') && $triggerInfo['is_trigger']) {
    error_log("=== TRIGGER DETECTED ===");

    if ($triggerInfo['is_callback']) {
        error_log("Callback handler (Telegram + SMS)");
        $caller_number = $data['caller_id'] ?? '';
        require_once __DIR__ . '/callback_request_handler.php';
        handleCallbackRequest($caller_number);
    }

    echo json_encode(['status' => 'trigger_processed']);
    exit;
}

// GET — перевірка статусу
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    echo json_encode(['status' => 'active', 'time' => date('Y-m-d H:i:s')]);
    exit;
}

// POST — IVR та інші події
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    writeLog("Event: $event, from: " . ($data['caller_id'] ?? ''));

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
        case 'NOTIFY_INTERNAL':
            handleNotifyInternal($data);
            break;
        default:
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
    echo json_encode(['status' => 'ok']);
}

function handleIvrResponse($data) {
    $caller_id = $data['caller_id'] ?? 'Unknown';
    $digits    = $data['wait_dtmf']['digits'] ?? '';

    writeLog("IVR: $caller_id натиснув '$digits'");

    switch ($digits) {
        case '1':
            // Кнопка 1 → Telegram-сповіщення + SMS клієнту
            writeLog("IVR: Кнопка 1 — callback → **#518196-103");
            echo json_encode(['redirect' => '**#518196-103']);
            break;

        case '2':
            // Кнопка 2 → голосове (Zadarma), PHP нічого не робить
            writeLog("IVR: Кнопка 2 — голосове меню");
            echo json_encode(['status' => 'ok']);
            break;

        case '3':
            // Кнопка 3 → переадресація на лікаря
            writeLog("IVR: Кнопка 3 — лікар → **#518196-104");
            echo json_encode(['redirect' => '**#518196-104']);
            break;

        default:
            writeLog("IVR: Невідомий вибір '$digits'");
            echo json_encode([
                'ivr_say'   => ['text' => 'Невірний вибір. Спробуйте ще раз.', 'language' => 'ua'],
                'wait_dtmf' => ['timeout' => 10, 'max_digits' => 1, 'attempts' => 2, 'name' => 'main_menu']
            ]);
            break;
    }
}

function handleCallEnd($data) {
    writeLog("Кінець дзвінка від " . ($data['caller_id'] ?? '') . ", тривалість: " . ($data['duration'] ?? 0) . "с");
    echo json_encode(['status' => 'ok']);
}

function handleNotifyInternal($data) {
    global $config;
    $caller_id = $data['caller_id'] ?? 'Unknown';
    $internal  = $data['internal'] ?? '';

    writeLog("NOTIFY_INTERNAL: $caller_id → $internal");

    switch ($internal) {
        case '103':
            writeLog("Кнопка 1 — callback handler від $caller_id");
            require_once __DIR__ . '/callback_request_handler.php';
            handleCallbackRequest($caller_id);
            break;

        case '104':
            // Дзвінок вже переданий на internal 104 через redirect в handleIvrResponse
            writeLog("Кнопка 3 — дзвінок переданий на лікаря (ext 104) від $caller_id");
            break;

        default:
            writeLog("Невідомий internal: $internal");
            break;
    }

    echo json_encode(['status' => 'internal_processed']);
}

?>

