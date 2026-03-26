<?php
/**
 * Instagram Messenger — PHP Proxy
 * POST /messenger/send.php
 * Body: { "recipient_id": "...", "message_text": "..." }
 */

header('Content-Type: application/json; charset=utf-8');

// ── CONFIG ─────────────────────────────────────────────────────────────────
define('PAGE_ACCESS_TOKEN', 'EAAQLGOh0CyYBRCjOVDovzRrWucgH3X9LXDhTquvg7Hu39RocptXxTr9PcJ57gDeEr1XcZCnG01JazUSSZAZC81u5PYv3opdUvDRGQMAuXGMo3xZCXwDsS8xExqghqFPcjcLk5PTC2G0dQXrCTTZBTRztqVf5Qc9oYrlGAyLBkeAZAsDeob2mZCYBCyg3r9Inqvutexg9NvBDz9JXxZCTJDMZD');
define('IG_USER_ID',        '17841433380804698');
define('GRAPH_VERSION',     'v19.0');

// ── CORS (тільки з того самого домену) ───────────────────────────────────
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin) {
    $host = parse_url($origin, PHP_URL_HOST) ?? '';
    if (str_ends_with($host, 'gomon.ua') || str_ends_with($host, 'gomonclinic.com') || $host === 'localhost') {
        header("Access-Control-Allow-Origin: $origin");
        header('Access-Control-Allow-Methods: POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type');
    }
}
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

// ── ТІЛЬКИ POST ────────────────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// ── ПАРСИНГ ТІЛА ──────────────────────────────────────────────────────────
$raw  = file_get_contents('php://input');
$body = json_decode($raw, true);

if (!$body || !isset($body['recipient_id'], $body['message_text'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Required fields: recipient_id, message_text']);
    exit;
}

$recipient_id = trim($body['recipient_id']);
$message_text = trim($body['message_text']);

if ($recipient_id === '' || $message_text === '') {
    http_response_code(400);
    echo json_encode(['error' => 'recipient_id and message_text must not be empty']);
    exit;
}

// ── ВИКЛИК GRAPH API ──────────────────────────────────────────────────────
$url     = 'https://graph.facebook.com/' . GRAPH_VERSION . '/' . IG_USER_ID . '/messages';
$payload = json_encode([
    'recipient' => ['id' => $recipient_id],
    'message'   => ['text' => $message_text],
]);

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $payload,
    CURLOPT_HTTPHEADER     => [
        'Content-Type: application/json',
        'Authorization: Bearer ' . PAGE_ACCESS_TOKEN,
    ],
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => true,
]);

$response  = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_err  = curl_error($ch);
curl_close($ch);

if ($curl_err) {
    http_response_code(502);
    echo json_encode(['error' => 'cURL: ' . $curl_err]);
    exit;
}

http_response_code($http_code);
echo $response;
