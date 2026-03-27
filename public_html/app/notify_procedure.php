<?php
// notify_procedure.php — Telegram-сповіщення про реальну дію з підібраною процедурою
// Викликається тільки коли юзер: скопіював назву або перейшов в Instagram Direct

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}

// Завантажуємо конфігурацію з окремого файлу
require_once __DIR__ . '/config.php';

define('DR_GOMON_CHAT_ID', '7930079513');  // Телеграм ID доктора Гомон
define('DB_PATH', '/home/gomoncli/zadarma/users.db');

$raw  = file_get_contents('php://input');
$data = json_decode($raw, true);

if (!$data || empty($data['procedure'])) {
    echo json_encode(['ok' => false]);
    exit;
}

$procedure  = trim($data['procedure']);
$user_name  = trim($data['user_name']  ?? '');
$user_phone = trim($data['user_phone'] ?? '');
$action     = trim($data['action']     ?? ''); // 'copy' | 'instagram'

// ── ХЕЛПЕРИ ──────────────────────────────────────────────────────────────────

function lookup_telegram_user(string $phone): ?array {
    if (!file_exists(DB_PATH)) return null;
    try {
        $db  = new PDO('sqlite:' . DB_PATH);
        $suf = substr(preg_replace('/\D/', '', $phone), -9);
        $st  = $db->prepare(
            "SELECT telegram_id, username FROM users WHERE phone LIKE :p LIMIT 1"
        );
        $st->execute([':p' => '%' . $suf]);
        $row = $st->fetch(PDO::FETCH_ASSOC);
        return $row ?: null;
    } catch (Exception $e) {
        return null;
    }
}

function format_phone_link(string $phone): string {
    $digits = preg_replace('/\D/', '', $phone);
    if (strlen($digits) === 10) $digits = '38' . $digits;
    return '<a href="tel:+' . $digits . '">+' . $digits . '</a>';
}

function format_tg_link(?array $tg): string {
    if (!$tg) return '';
    if (!empty($tg['username']))
        return ' · <a href="https://t.me/' . htmlspecialchars($tg['username'], ENT_XML1) . '">@' . htmlspecialchars($tg['username'], ENT_XML1) . '</a>';
    if (!empty($tg['telegram_id']))
        return ' · <a href="tg://user?id=' . (int)$tg['telegram_id'] . '">Telegram</a>';
    return '';
}

// ── ВІДПРАВКА ─────────────────────────────────────────────────────────────────

$tg_user   = $user_phone ? lookup_telegram_user($user_phone) : null;
$phone_str = $user_phone ? format_phone_link($user_phone) : '';
$tg_link   = format_tg_link($tg_user);

$action_label = match($action) {
    'copy'      => '📋 <b>Скопіював назву процедури</b>',
    'instagram' => '📱 <b>Перейшов в Instagram Direct</b>',
    default     => '🌸 <b>Підібрана процедура</b>',
};

$lines   = [];
$lines[] = $action_label;
$lines[] = "";
if ($user_name)  $lines[] = "👤 <b>Ім'я:</b> " . htmlspecialchars($user_name, ENT_XML1);
if ($phone_str)  $lines[] = "📱 <b>Телефон:</b> " . $phone_str . $tg_link;
$lines[] = "";
$lines[] = "💆 <b>Процедура:</b> " . htmlspecialchars($procedure, ENT_XML1);
$lines[] = "";
$lines[] = "<i>Підібрано AI-асистентом клініки</i>";

$payload = [
    'chat_id'    => DR_GOMON_CHAT_ID,
    'text'       => implode("\n", $lines),
    'parse_mode' => 'HTML',
];

$ch = curl_init('https://api.telegram.org/bot' . TELEGRAM_BOT_TOKEN . '/sendMessage');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => json_encode($payload),
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
    CURLOPT_TIMEOUT        => 10,
]);
curl_exec($ch);
curl_close($ch);

echo json_encode(['ok' => true]);
