<?php
/**
 * Instagram Messenger — PHP Proxy (v25.0 Instagram API)
 * POST /messenger/send.php
 * Body: { "recipient_id": "...", "message_text": "...", "token": "..." }
 */

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

require_once dirname(__DIR__) . '/app/config.php';

define('GRAPH_VERSION', 'v25.0');

// ── CORS ───────────────────────────────────────────────────────────────────
$allowed_hosts = ['gomonclinic.com', 'www.gomonclinic.com', 'drgomon.beauty', 'www.drgomon.beauty'];
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin) {
    $host = parse_url($origin, PHP_URL_HOST) ?? '';
    if (in_array($host, $allowed_hosts, true)) {
        header("Access-Control-Allow-Origin: $origin");
        header('Access-Control-Allow-Methods: POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type');
    }
}
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// ── PARSE BODY ─────────────────────────────────────────────────────────────
$raw  = file_get_contents('php://input');
$body = json_decode($raw, true);

if (!$body || !isset($body['recipient_id'], $body['message_text'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Required fields: recipient_id, message_text']);
    exit;
}

$recipient_id = trim($body['recipient_id']);
$message_text = trim($body['message_text']);
$token        = trim($body['token'] ?? '') ?: IG_FALLBACK_TOKEN;

if ($recipient_id === '' || $message_text === '') {
    http_response_code(400);
    echo json_encode(['error' => 'recipient_id and message_text must not be empty']);
    exit;
}

// ── CALL INSTAGRAM GRAPH API ───────────────────────────────────────────────
$url     = 'https://graph.instagram.com/' . GRAPH_VERSION . '/me/messages';
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
        'Authorization: Bearer ' . $token,
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
