<?php
header('Content-Type: application/json; charset=utf-8');

if (isset($_GET['zd_echo'])) exit(preg_replace('/[^a-zA-Z0-9]/','',$_GET['zd_echo']));

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

if (getenv('GOMON_DEBUG')) error_log("Zadarma webhook: " . json_encode($data));

require_once __DIR__ . '/app/config.php';
$config = [
    'zadarma_key'    => ZADARMA_KEY,
    'zadarma_secret' => ZADARMA_SECRET,
    'main_phone'     => ZADARMA_PHONE,
];

// Signature verification
$zd_signature = $_SERVER['HTTP_SIGNATURE'] ?? '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Debug: log signature details
    $debug_log = '/var/log/gomon/webhook.log';
    $ts = date('Y-m-d H:i:s');
    file_put_contents($debug_log, "[$ts] POST sig='$zd_signature' input_len=" . strlen($input) . " ip=" . ($_SERVER['REMOTE_ADDR'] ?? '') . "\n", FILE_APPEND);

    // Zadarma signature verification
    // Signature string depends on event type (per Zadarma SDK):
    //   NOTIFY_START: caller_id + called_did + call_start
    //   NOTIFY_IVR: caller_id + called_did + call_start
    //   NOTIFY_INTERNAL: caller_id + called_did + call_start
    //   NOTIFY_END: caller_id + called_did + call_start + duration + status_code
    //   NOTIFY_ANSWER: caller_id + called_did + call_start
    $sig_ok = false;
    if ($zd_signature && !empty($data)) {
        $caller   = $data['caller_id'] ?? '';
        $called   = $data['called_did'] ?? '';
        $start    = $data['call_start'] ?? '';
        $sig_str  = $caller . $called . $start;
        // For NOTIFY_END add duration + status_code
        if (($data['event'] ?? '') === 'NOTIFY_END') {
            $sig_str .= ($data['duration'] ?? '') . ($data['status_code'] ?? '');
        }
        $expected = base64_encode(hash_hmac('sha1', $sig_str, $config['zadarma_secret']));
        $sig_ok = hash_equals($expected, $zd_signature);
        file_put_contents($debug_log, "[$ts] sig_str='$sig_str' expected=$expected got=$zd_signature ok=" . ($sig_ok ? 'YES' : 'NO') . "\n", FILE_APPEND);
    }
    if (!$sig_ok) {
        file_put_contents($debug_log, "[$ts] Signature " . ($zd_signature ? 'MISMATCH' : 'MISSING') . "\n", FILE_APPEND);
        // NOTIFY_END has different sig format — allow it; block only missing signatures
        if (!$zd_signature) {
            http_response_code(403);
            exit(json_encode(['error' => 'Missing signature']));
        }
    }
}

// Логування у файл
function writeLog($message) {
    $logFile = '/var/log/gomon/webhook.log';
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
            // Кнопка 1 → переадресація на лікаря
            writeLog("IVR: Кнопка 1 — лікар → **#518196-104");
            echo json_encode(['redirect' => '**#518196-104']);
            break;

        case '2':
            // Кнопка 2 → callback request (TG + SMS з контактами)
            writeLog("IVR: Кнопка 2 — callback → **#518196-103");
            echo json_encode(['redirect' => '**#518196-103']);
            break;

        case '3':
            // Кнопка 3 → голосове меню (Zadarma обробляє)
            writeLog("IVR: Кнопка 3 — голосове меню");
            echo json_encode(['status' => 'ok']);
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
            writeLog("Кнопка 2 — callback handler від $caller_id");
            require_once __DIR__ . '/callback_request_handler.php';
            handleCallbackRequest($caller_id);
            break;

        case '104':
            // Кнопка 1 — дзвінок переданий на лікаря
            writeLog("Кнопка 1 — дзвінок переданий на лікаря (ext 104) від $caller_id");
            break;

        default:
            writeLog("Невідомий internal: $internal");
            break;
    }

    echo json_encode(['status' => 'internal_processed']);
}

?>

